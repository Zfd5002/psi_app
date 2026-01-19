from __future__ import annotations

from sqlalchemy.orm import Session

from psi.core.models import DataRecord, Evidence, File as StoredFile


def search_all(db: Session, *, q: str = "") -> dict:
    q = (q or "").strip()
    like = f"%{q}%"

    records = []
    evidence = []
    files = []
    if q:
        records = (
            db.query(DataRecord)
            .filter(
                (DataRecord.title.like(like))
                | (DataRecord.notes.like(like))
                | (DataRecord.params_json.like(like))
                | (DataRecord.results_json.like(like))
            )
            .order_by(DataRecord.created_at.desc())
            .limit(50)
            .all()
        )
        evidence = (
            db.query(Evidence)
            .filter(
                (Evidence.summary.like(like)) | (Evidence.details.like(like)) | (Evidence.evidence_type.like(like))
            )
            .order_by(Evidence.created_at.desc())
            .limit(50)
            .all()
        )
        files = (
            db.query(StoredFile)
            .filter((StoredFile.original_name.like(like)) | (StoredFile.sha256.like(like)))
            .order_by(StoredFile.created_at.desc())
            .limit(50)
            .all()
        )

    return {"q": q, "records": records, "evidence": evidence, "files": files}
