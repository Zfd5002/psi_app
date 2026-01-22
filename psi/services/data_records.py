from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import AuditEvent, Batch, DataRecord, Evidence, EvidenceCitation, File as StoredFile, FileLink, Molecule, Program
from psi.core.registry import REGISTRY, normalize_data_record_for_storage
from psi.core.utils import model_to_dict, now_utc
from psi.services.files import attach_files


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
    params_json: str = "{}",
    results_json: str = "{}",
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

    rec = DataRecord(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        domain=domain,
        data_type=data_type,
        method=method,
        title=title.strip(),
        notes=notes.strip() or None,
        run_date=run_date.strip() or None,
        params_json=params_json.strip() or "{}",
        results_json=results_json.strip() or "{}",
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(rec)
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
    params_json: str = "{}",
    results_json: str = "{}",
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

    before = model_to_dict(rec)
    rec.program_id = program_id
    rec.molecule_id = molecule_id
    rec.batch_id = batch_id
    rec.domain = domain
    rec.data_type = data_type
    rec.method = method
    rec.title = title.strip()
    rec.notes = notes.strip() or None
    rec.run_date = run_date.strip() or None
    rec.params_json = params_json.strip() or "{}"
    rec.results_json = results_json.strip() or "{}"
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
        "params": _load_json_field(rec.params_json),
        "results": _load_json_field(rec.results_json),
        "evidence": evidence,
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
