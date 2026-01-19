from __future__ import annotations

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import AuditEvent, Batch, DataRecord, DecisionSnapshot, Evidence, Molecule, Program
from psi.core.utils import model_to_dict, now_utc


def list_programs(db: Session) -> list[Program]:
    return db.query(Program).order_by(Program.created_at.desc()).all()


def get_program(db: Session, program_id: int) -> Program | None:
    return db.get(Program, program_id)


def get_program_detail(db: Session, program_id: int) -> dict:
    p = get_program(db, program_id)
    if not p:
        raise KeyError("Program not found")

    molecules = db.query(Molecule).filter(Molecule.program_id == program_id).order_by(Molecule.created_at.desc()).all()
    recent_batches = (
        db.query(Batch)
        .join(Molecule)
        .filter(Molecule.program_id == program_id)
        .order_by(Batch.created_at.desc())
        .limit(10)
        .all()
    )
    recent_data = (
        db.query(DataRecord)
        .filter(DataRecord.program_id == program_id)
        .order_by(DataRecord.created_at.desc())
        .limit(10)
        .all()
    )
    recent_evidence = (
        db.query(Evidence)
        .filter(Evidence.program_id == program_id)
        .order_by(Evidence.created_at.desc())
        .limit(10)
        .all()
    )
    recent_decisions = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.program_id == program_id)
        .order_by(DecisionSnapshot.created_at.desc())
        .limit(10)
        .all()
    )
    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Program", AuditEvent.entity_id == program_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    return {
        "program": p,
        "molecules": molecules,
        "recent_batches": recent_batches,
        "recent_data": recent_data,
        "recent_evidence": recent_evidence,
        "recent_decisions": recent_decisions,
        "audits": audits,
    }


def create_program(db: Session, *, name: str, description: str = "") -> Program:
    p = Program(
        name=name.strip(),
        description=description.strip(),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    record_audit(db, entity_type="Program", entity_id=p.id, action="create", before=None, after=model_to_dict(p))
    db.commit()
    return p


def update_program(db: Session, *, program_id: int, name: str, description: str = "", reason: str = "") -> Program:
    p = get_program(db, program_id)
    if not p:
        raise KeyError("Program not found")
    before = model_to_dict(p)
    p.name = name.strip()
    p.description = description.strip()
    p.updated_at = now_utc()
    db.add(p)
    db.commit()
    record_audit(
        db,
        entity_type="Program",
        entity_id=p.id,
        action="update",
        before=before,
        after=model_to_dict(p),
        reason=reason or None,
    )
    db.commit()
    return p
