from __future__ import annotations

from pathlib import Path
from typing import Sequence

from sqlalchemy.orm import Session

from psi.core.models import File as StoredFile
from psi.core.models import FileLink
from psi.core.storage import StorageConfig, add_files_to_entity, delete_file_link_and_cleanup, resolve_file_path


def attach_files(
    db: Session,
    *,
    storage: StorageConfig,
    entity_type: str,
    entity_id: int,
    uploads: Sequence[tuple[str, str, bytes]],
    # v1.2.6: typed linkage + optional provenance (applied to all uploads in call)
    role: str | None = None,
    label: str | None = None,
    source_kind: str | None = None,
    source_path: str | None = None,
    collected_at: str | None = None,
    instrument: str | None = None,
    operator: str | None = None,
    run_id: str | None = None,
    tags_json: str | None = None,
    notes: str | None = None,
) -> list[FileLink]:
    return add_files_to_entity(
        db,
        cfg=storage,
        entity_type=entity_type,
        entity_id=entity_id,
        uploads=uploads,
        role=role,
        label=label,
        source_kind=source_kind,
        source_path=source_path,
        collected_at=collected_at,
        instrument=instrument,
        operator=operator,
        run_id=run_id,
        tags_json=tags_json,
        notes=notes,
    )

def delete_filelink(
    db: Session,
    *,
    storage: StorageConfig,
    filelink_id: int,
) -> None:
    delete_file_link_and_cleanup(db, cfg=storage, filelink_id=filelink_id)


def get_file(db: Session, file_id: int) -> StoredFile | None:
    return db.get(StoredFile, file_id)


def get_download_path(storage: StorageConfig, stored: StoredFile) -> Path:
    return resolve_file_path(storage, stored)


def list_files(
    db: Session,
    *,
    q: str | None = None,
    source_kind: str | None = None,
    sha256_prefix: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[StoredFile]:
    """Deterministic file listing for the registry page."""
    qry = db.query(StoredFile)
    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(StoredFile.original_name.like(like))
    if source_kind:
        qry = qry.filter(StoredFile.source_kind == source_kind)
    if sha256_prefix:
        pref = sha256_prefix.strip()
        qry = qry.filter(StoredFile.sha256.like(f"{pref}%"))
    qry = qry.order_by(StoredFile.created_at.desc(), StoredFile.id.desc())
    if offset:
        qry = qry.offset(int(offset))
    if limit:
        qry = qry.limit(int(limit))
    return list(qry.all())


def list_links_for_entity(db: Session, *, entity_type: str, entity_id: int) -> list[FileLink]:
    qry = (
        db.query(FileLink)
        .filter(FileLink.entity_type == entity_type, FileLink.entity_id == entity_id)
        .order_by(FileLink.created_at.desc(), FileLink.id.desc())
    )
    return list(qry.all())


def set_filelink_role(db: Session, *, filelink_id: int, role: str, label: str | None = None) -> FileLink | None:
    link = db.get(FileLink, filelink_id)
    if not link:
        return None
    link.role = (role or "other")
    link.label = (label or None)
    db.commit()
    db.refresh(link)
    return link


from psi.core.models import FileDerivation


def create_derivation(
    db: Session,
    *,
    parent_file_id: int,
    child_file_id: int,
    transform: str | None = None,
    tool_name: str | None = None,
    tool_version: str | None = None,
) -> FileDerivation:
    d = FileDerivation(
        parent_file_id=parent_file_id,
        child_file_id=child_file_id,
        transform=(transform or None),
        tool_name=(tool_name or None),
        tool_version=(tool_version or None),
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def list_derivations_for_file(db: Session, *, file_id: int) -> list[FileDerivation]:
    qry = (
        db.query(FileDerivation)
        .filter((FileDerivation.parent_file_id == file_id) | (FileDerivation.child_file_id == file_id))
        .order_by(FileDerivation.created_at.desc(), FileDerivation.id.desc())
    )
    return list(qry.all())
