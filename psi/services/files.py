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
) -> list[FileLink]:
    return add_files_to_entity(db, cfg=storage, entity_type=entity_type, entity_id=entity_id, uploads=uploads)


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
