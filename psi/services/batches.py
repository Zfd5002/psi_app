from __future__ import annotations

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.batch_id import next_batch_id
from psi.core.models import AuditEvent, Batch, DataRecord, Evidence, File as StoredFile, FileLink, Molecule
from psi.core.utils import model_to_dict, now_utc


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
