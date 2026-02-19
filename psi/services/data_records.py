from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import AuditEvent, Batch, DataRecord, Evidence, EvidenceCitation, File as StoredFile, FileLink, Molecule, Program
from psi.core.registry import REGISTRY, normalize_data_record_for_storage
from psi.core.utils import model_to_dict, now_utc
from psi.services.files import attach_files
from psi.services.measurements import extract_measurements, upsert_measurements, upsert_measurements_force


def _infer_primary_result_text(results_json: str) -> str | None:
    """Best-effort primary result string for batch summaries."""
    import json
    if not results_json:
        return None
    try:
        obj = json.loads(results_json)
    except Exception:
        return results_json.strip()[:200] or None
    if isinstance(obj, dict):
        for k in ("primary_result", "primary", "summary", "result", "value", "text"):
            v = obj.get(k)
            if isinstance(v, (str, int, float)):
                s = str(v).strip()
                if s:
                    return s[:200]
        # pick first scalar
        for v in obj.values():
            if isinstance(v, (str, int, float)):
                s = str(v).strip()
                if s:
                    return s[:200]
        return None
    if isinstance(obj, (str, int, float)):
        s = str(obj).strip()
        return s[:200] or None
    return None

def _parse_run_at(run_at: Any) -> Optional[datetime]:
    """
    Parse run_at into a datetime or return None.

    Accepts:
      - None / "" -> None
      - datetime -> returned as-is
      - ISO strings:
          "YYYY-MM-DD"
          "YYYY-MM-DDTHH:MM:SS"
          "YYYY-MM-DD HH:MM:SS"
          (also tolerates trailing 'Z' by stripping it)
    """
    if run_at is None:
        return None
    if isinstance(run_at, str):
        s = run_at.strip()
        if not s:
            return None
        # tolerate common variants
        s = s.replace(" ", "T")
        if s.endswith("Z"):
            s = s[:-1]
        # date-only
        if len(s) == 10:
            # "YYYY-MM-DD"
            return datetime.fromisoformat(s + "T00:00:00")
        try:
            return datetime.fromisoformat(s)
        except Exception:
            raise ValueError(f"Invalid run_at value: {run_at!r}")
    if isinstance(run_at, datetime):
        return run_at
    raise ValueError(f"Invalid run_at type: {type(run_at).__name__}")


def _jsonish_to_str(value: Any, *, default: str = "{}") -> str:
    """Normalize JSON-ish inputs to a compact string.

    Contract (v1.2.3b stabilization): callers may provide either a JSON string
    *or* a Python object (dict/list/etc.). Storage remains TEXT containing JSON.

    - None/"" -> default
    - str -> stripped (if empty -> default)
    - dict/list/number/bool -> json.dumps(...)

    This is intentionally conservative and must not raise for typical inputs.
    """
    if value is None:
        return default
    if isinstance(value, str):
        s = value.strip()
        return s if s else default
    try:
        # Ensure stable JSON (helps idempotence + diffs)
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        # Last resort: store a string representation
        s = str(value).strip()
        return s if s else default


def list_data_records(db: Session) -> dict:
    records = db.query(DataRecord).order_by(DataRecord.created_at.desc()).limit(200).all()
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    return {"records": records, "programs": programs, "molecules": molecules, "batches": batches}


def get_data_record(db: Session, record_id: int) -> DataRecord | None:
    return db.get(DataRecord, record_id)




def create_data_record(
    db: Session,
    *,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    domain: str,
    data_type: str,
    method: str,
    title: str,
    notes: str = "",
    run_date: str = "",
    run_at: str = "",
    params_json: Any = "{}",
    results_json: Any = "{}",
    uploads: Optional[list[tuple[str, str, bytes]]] = None,
    storage=None,
    reason: Optional[str] = None,
) -> DataRecord:
    # normalize domain/data_type/method when safe (keeps legacy values when not mappable)
    domain, data_type, method = normalize_data_record_for_storage(domain, data_type, method)

    # enforce batch requirement for experimental types
    program_level = set(REGISTRY.get("program_level_data_types", [])) | set(REGISTRY.get("legacy_program_level_data_types", []))
    requiring_batch = set(REGISTRY.get("data_types_requiring_batch", [])) | set(REGISTRY.get("legacy_data_types_requiring_batch", []))
    if (data_type in requiring_batch or data_type not in program_level) and not batch_id:
        # canonical: anything not explicitly program-level is treated as batch-scoped
        raise ValueError("batch_id is required for this data type")

    params_s = _jsonish_to_str(params_json, default="{}")
    results_s = _jsonish_to_str(results_json, default="{}")

    # Prefer explicit run_date (ISO date). If absent, derive from run_at when provided.
    run_date_s = (run_date or '').strip() or None
    if not run_date_s and (run_at or '').strip():
        dt = _parse_run_at(run_at)
        if dt is not None:
            run_date_s = dt.date().isoformat()

    rec = DataRecord(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        domain=domain,
        data_type=data_type,
        method=method,
        title=title.strip(),
        notes=notes.strip() or None,
        run_date=run_date_s,
        params_json=params_s,
        results_json=results_s,
        raw_inputs_json=params_s,
        derived_outputs_json=results_s,
        primary_result_text=_infer_primary_result_text(results_s),
        is_included=1,
        excluded_reason=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    specs = extract_measurements(
        data_type=rec.data_type,
        method=rec.method,
        results_json=rec.results_json,
        params_json=rec.params_json,
    )
    if specs:
        # New record: safe upsert is fine.
        upsert_measurements(db, record_id=rec.id, measurements=specs)
        db.commit()
        db.refresh(rec)

    if uploads and storage is not None:
        attach_files(db, storage=storage, entity_type="DataRecord", entity_id=rec.id, uploads=uploads)

    record_audit(
        db,
        entity_type="DataRecord",
        entity_id=rec.id,
        action="create",
        before=None,
        after=model_to_dict(rec),
        reason=reason,
    )
    db.commit()
    return rec


def update_data_record(
    db: Session,
    *,
    record_id: int,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    domain: str,
    data_type: str,
    method: str,
    title: str,
    notes: str = "",
    run_date: str = "",
    run_at: str = "",
    params_json: Any = "{}",
    results_json: Any = "{}",
    uploads: Optional[list[tuple[str, str, bytes]]] = None,
    storage=None,
    reason: str = "",
) -> DataRecord:
    rec = get_data_record(db, record_id)
    if not rec:
        raise KeyError("DataRecord not found")

    # normalize domain/data_type/method when safe (keeps legacy values when not mappable)
    domain, data_type, method = normalize_data_record_for_storage(domain, data_type, method)

    program_level = set(REGISTRY.get("program_level_data_types", [])) | set(REGISTRY.get("legacy_program_level_data_types", []))
    requiring_batch = set(REGISTRY.get("data_types_requiring_batch", [])) | set(REGISTRY.get("legacy_data_types_requiring_batch", []))
    if (data_type in requiring_batch or data_type not in program_level) and not batch_id:
        raise ValueError("batch_id is required for this data type")

    params_s = _jsonish_to_str(params_json, default="{}")
    results_s = _jsonish_to_str(results_json, default="{}")

    before = model_to_dict(rec)
    rec.program_id = program_id
    rec.molecule_id = molecule_id
    rec.batch_id = batch_id
    rec.domain = domain
    rec.data_type = data_type
    rec.method = method
    rec.title = title.strip()
    rec.notes = notes.strip() or None
    run_date=run_date_s,
    rec.params_json = params_s
    rec.results_json = results_s
    rec.raw_inputs_json = params_s
    rec.derived_outputs_json = results_s
    rec.primary_result_text = _infer_primary_result_text(results_s)
    rec.updated_at = now_utc()
    db.add(rec)
    db.commit()

    specs = extract_measurements(
        data_type=rec.data_type,
        method=rec.method,
        results_json=rec.results_json,
        params_json=rec.params_json,
    )
    if specs:
        # Updating an existing record is an explicit user action; keep measurements in sync.
        upsert_measurements_force(db, record_id=rec.id, measurements=specs)
        rec.updated_at = now_utc()
        db.add(rec)
        db.commit()

    if uploads and storage is not None:
        attach_files(db, storage=storage, entity_type="DataRecord", entity_id=rec.id, uploads=uploads)

    record_audit(
        db,
        entity_type="DataRecord",
        entity_id=rec.id,
        action="update",
        before=before,
        after=model_to_dict(rec),
        reason=reason or None,
    )
    db.commit()
    return rec


def get_data_record_detail(db: Session, record_id: int) -> dict:
    rec = get_data_record(db, record_id)
    if not rec:
        raise KeyError("DataRecord not found")

    citations = db.query(EvidenceCitation).filter(EvidenceCitation.data_record_id == record_id).all()
    ev_ids = [c.evidence_id for c in citations]
    evidence = db.query(Evidence).filter(Evidence.id.in_(ev_ids)).all() if ev_ids else []

    file_links = (
        db.query(FileLink)
        .filter(FileLink.entity_type == "DataRecord", FileLink.entity_id == record_id)
        .order_by(FileLink.created_at.desc())
        .all()
    )
    files = db.query(StoredFile).filter(StoredFile.id.in_([fl.file_id for fl in file_links])).all() if file_links else []
    files_by_id = {f.id: f for f in files}

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "DataRecord", AuditEvent.entity_id == record_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    return {
        "record": rec,
        "measurements": list(rec.measurements) if getattr(rec, "measurements", None) is not None else [],
        "params": _load_json_field(rec.params_json),
        "results": _load_json_field(rec.results_json),
        "evidence_citing": evidence,
        "file_links": file_links,
        "files_by_id": files_by_id,
        "audits": audits,
    }


def get_form_context(db: Session) -> dict:
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    return {"programs": programs, "molecules": molecules, "batches": batches}


def _load_json_field(s: str) -> dict[str, Any]:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def api_data_records(
    db: Session,
    *,
    program_id: int,
    molecule_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    q: str = "",
) -> dict:
    query = db.query(DataRecord).filter(DataRecord.program_id == program_id)
    if batch_id:
        query = query.filter((DataRecord.batch_id == batch_id) | (DataRecord.batch_id.is_(None)))
    elif molecule_id:
        query = query.filter((DataRecord.molecule_id == molecule_id) | (DataRecord.molecule_id.is_(None)))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((DataRecord.title.like(like)) | (DataRecord.notes.like(like)))
    rows = query.order_by(DataRecord.created_at.desc()).limit(200).all()

    return {
        "records": [
            {
                "id": r.id,
                "title": r.title,
                "domain": r.domain,
                "data_type": r.data_type,
                "method": r.method,
                "run_date": r.run_date,
                "batch_id": r.batch_id,
            }
            for r in rows
        ]
    }
