from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.decision_engine import load_rules, run_decision
from psi.core.models import Batch, DataRecord, DecisionSnapshot, Evidence, EvidenceCitation, File as StoredFile, FileLink, Molecule, Program
from psi.core.utils import json_dumps_compact, model_to_dict, now_utc


def list_decision_snapshots(db: Session) -> list[DecisionSnapshot]:
    return db.query(DecisionSnapshot).order_by(DecisionSnapshot.created_at.desc()).limit(200).all()


def get_decision_new_context(db: Session, rules_path: str) -> dict:
    programs = db.query(Program).order_by(Program.name.asc()).all()
    molecules = db.query(Molecule).order_by(Molecule.primary_id.asc()).all()
    batches = db.query(Batch).order_by(Batch.created_at.desc()).all()
    rules = load_rules(rules_path)
    decision_keys = list(rules.get("decisions", {}).keys())
    return {
        "programs": programs,
        "molecules": molecules,
        "batches": batches,
        "decision_keys": decision_keys,
        "rules_version": rules.get("version"),
    }


def run_and_snapshot(
    db: Session,
    *,
    rules_path: str,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    decision_key: str,
    assumptions_ack: bool,
) -> DecisionSnapshot:
    if not assumptions_ack:
        raise ValueError("Must acknowledge assumptions")

    rules = load_rules(rules_path)
    if decision_key not in rules.get("decisions", {}):
        raise ValueError("Invalid decision")

    q = db.query(Evidence).filter(Evidence.program_id == program_id)
    if batch_id:
        q = q.filter(
            (Evidence.molecule_id.is_(None) & Evidence.batch_id.is_(None))
            | ((Evidence.molecule_id == molecule_id) & Evidence.batch_id.is_(None))
            | (Evidence.batch_id == batch_id)
        )
    elif molecule_id:
        q = q.filter(
            (Evidence.molecule_id.is_(None) & Evidence.batch_id.is_(None))
            | ((Evidence.molecule_id == molecule_id) & Evidence.batch_id.is_(None))
        )
    else:
        q = q.filter(Evidence.molecule_id.is_(None), Evidence.batch_id.is_(None))

    evidence = q.all()
    result = run_decision(rules, decision_key, evidence)

    snap = DecisionSnapshot(
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
        decision_key=decision_key,
        rules_version=str(rules.get("version")),
        inputs_json=json_dumps_compact({
            "program_id": program_id,
            "molecule_id": molecule_id,
            "batch_id": batch_id,
            "decision_key": decision_key,
        }),
        outputs_json=json_dumps_compact(result),
        evidence_ids_json=json_dumps_compact(result.get("evidence_ids_used", [])),
        created_at=now_utc(),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    record_audit(db, entity_type="DecisionSnapshot", entity_id=snap.id, action="create", before=None, after=model_to_dict(snap))
    db.commit()

    return snap


def get_snapshot_detail(db: Session, snap_id: int) -> dict:
    snap = db.get(DecisionSnapshot, snap_id)
    if not snap:
        raise KeyError("DecisionSnapshot not found")

    output = json.loads(snap.outputs_json)
    evidence_ids = output.get("evidence_ids_used", [])
    evidence = db.query(Evidence).filter(Evidence.id.in_(evidence_ids)).all() if evidence_ids else []

    citations = db.query(EvidenceCitation).filter(EvidenceCitation.evidence_id.in_(evidence_ids)).all() if evidence_ids else []
    dr_ids = sorted({c.data_record_id for c in citations})
    data_records = db.query(DataRecord).filter(DataRecord.id.in_(dr_ids)).all() if dr_ids else []

    dr_file_links = db.query(FileLink).filter(FileLink.entity_type == "DataRecord", FileLink.entity_id.in_(dr_ids)).all() if dr_ids else []
    file_ids = sorted({fl.file_id for fl in dr_file_links})
    files = db.query(StoredFile).filter(StoredFile.id.in_(file_ids)).all() if file_ids else []

    files_by_id = {f.id: f for f in files}
    file_links_by_dr: dict[int, list[FileLink]] = {}
    for fl in dr_file_links:
        file_links_by_dr.setdefault(fl.entity_id, []).append(fl)

    return {
        "snap": snap,
        "output": output,
        "evidence": evidence,
        "citations": citations,
        "data_records": data_records,
        "files_by_id": files_by_id,
        "file_links_by_dr": file_links_by_dr,
    }
