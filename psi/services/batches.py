from __future__ import annotations

import json

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.batch_id import next_batch_id
from psi.core.models import AuditEvent, Batch, DataRecord, DecisionSnapshot, Evidence, File as StoredFile, FileLink, Molecule
from psi.core.utils import model_to_dict, now_utc

from psi.services.di.snapshot_diff import compute_snapshot_diff_struct


def list_batches(db: Session) -> tuple[list[Batch], list[Molecule]]:
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    return batches, molecules


def get_batch(db: Session, batch_id: int) -> Batch | None:
    return db.get(Batch, batch_id)


def get_batch_detail(db: Session, batch_id: int) -> dict:
    b = get_batch(db, batch_id)
    if not b:
        raise KeyError("Batch not found")
    mol = db.get(Molecule, b.molecule_id)

    data_records = (
        db.query(DataRecord)
        .filter(DataRecord.batch_id == batch_id)
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.batch_id == batch_id)
        .order_by(Evidence.created_at.desc())
        .all()
    )

    # v1.2.9m: decision history for this batch (read-only surface)
    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.batch_id == batch_id)
        .order_by(DecisionSnapshot.created_at.asc(), DecisionSnapshot.id.asc())
        .all()
    )
    di_history: list[dict] = []
    prev_by_key: dict[str, dict] = {}
    for s in snaps:
        try:
            out = json.loads(s.outputs_json or "{}")
        except Exception:
            out = {}
        try:
            inn = json.loads(s.inputs_json or "{}")
        except Exception:
            inn = {}
        if not isinstance(out, dict) or not out.get("decision_state"):
            continue

        policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
        prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
        integ = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}

        gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
        if not gate_outcomes and isinstance(out.get("gates"), list):
            gate_outcomes = {
                str(g.get("gate_key")): {"status": g.get("status")}
                for g in out.get("gates")
                if isinstance(g, dict) and g.get("gate_key")
            }
        statuses = [str(v.get("status") or "") for v in (gate_outcomes or {}).values() if isinstance(v, dict)]
        pass_n = sum(1 for x in statuses if x == "pass")
        nonpass_n = sum(1 for x in statuses if x and x != "pass")
        blocker_n = len(out.get("blockers") or []) if isinstance(out.get("blockers"), list) else 0

        dk = str(s.decision_key or "")
        prev = prev_by_key.get(dk)
        drift_vs_prev = None
        prev_id = None
        if prev is not None:
            try:
                dr = compute_snapshot_diff_struct(out1=prev.get("out") or {}, in1=prev.get("in") or {}, out2=out, in2=inn)
                drift_vs_prev = str(dr.drift_label)
                prev_id = int(prev.get("snapshot_id") or 0)
            except Exception:
                drift_vs_prev = None
                prev_id = None

        di_history.append(
            {
                "snapshot_id": int(s.id),
                "created_at": s.created_at,
                "decision_key": dk,
                "policy_id": str(policy.get("policy_id") or ""),
                "policy_version": str(policy.get("policy_version") or ""),
                "summary": {
                    "decision_state": str(out.get("decision_state") or ""),
                    "gates_pass": int(pass_n),
                    "gates_nonpass": int(nonpass_n),
                    "blockers": int(blocker_n),
                },
                "integrity": {
                    "snapshot_content_hash": str(integ.get("snapshot_content_hash") or ""),
                    "evidence_fingerprint": str(integ.get("evidence_fingerprint") or ""),
                },
                "prev_snapshot_id": prev_id,
                "drift_vs_prev": drift_vs_prev,
            }
        )
        prev_by_key[dk] = {"snapshot_id": int(s.id), "out": out, "in": inn}

    di_history = list(reversed(di_history))
    file_links = (
        db.query(FileLink)
        .filter(FileLink.entity_type == "Batch", FileLink.entity_id == batch_id)
        .order_by(FileLink.created_at.desc())
        .all()
    )
    files_by_id = {}
    if file_links:
        fids = [fl.file_id for fl in file_links]
        files = db.query(StoredFile).filter(StoredFile.id.in_(fids)).all()
        files_by_id = {f.id: f for f in files}

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Batch", AuditEvent.entity_id == batch_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    return {
        "batch": b,
        "molecule": mol,
        "data_records": data_records,
        "evidence": evidence,
        "di_history": di_history,
        "file_links": file_links,
        "files_by_id": files_by_id,
        "audits": audits,
    }


def create_batch(
    db: Session,
    *,
    molecule_id: int,
    title: str = "",
    expression_notes: str = "",
    purification_notes: str = "",
) -> Batch:
    mol = db.get(Molecule, molecule_id)
    if not mol:
        raise ValueError("Invalid molecule")

    batch_code = next_batch_id(db, mol)
    b = Batch(
        molecule_id=molecule_id,
        batch_id=batch_code,
        title=title.strip() or None,
        expression_notes=expression_notes.strip() or None,
        purification_notes=purification_notes.strip() or None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    record_audit(db, entity_type="Batch", entity_id=b.id, action="create", before=None, after=model_to_dict(b))
    db.commit()
    return b


def update_batch(
    db: Session,
    *,
    batch_db_id: int,
    title: str = "",
    expression_notes: str = "",
    purification_notes: str = "",
    reason: str = "",
) -> Batch:
    b = get_batch(db, batch_db_id)
    if not b:
        raise KeyError("Batch not found")

    before = model_to_dict(b)
    b.title = title.strip() or None
    b.expression_notes = expression_notes.strip() or None
    b.purification_notes = purification_notes.strip() or None
    b.updated_at = now_utc()
    db.add(b)
    db.commit()

    record_audit(
        db,
        entity_type="Batch",
        entity_id=b.id,
        action="update",
        before=before,
        after=model_to_dict(b),
        reason=reason or None,
    )
    db.commit()
    return b
