from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from sqlalchemy.orm import Session

from .audit import record_audit
from .models import File as StoredFile
from .models import FileLink
from .utils import model_to_dict, now_utc, safe_filename, sha256_fileobj


@dataclass(frozen=True)
class StorageConfig:
    """Configuration for local file storage."""

    base_dir: Path

    @property
    def uploads_dir(self) -> Path:
        return self.base_dir / "uploads"


def ensure_storage(cfg: StorageConfig) -> None:
    cfg.uploads_dir.mkdir(parents=True, exist_ok=True)


def save_upload(
    db: Session,
    *,
    cfg: StorageConfig,
    filename: str,
    content_type: str,
    data: bytes,
    # v1.2.6: optional provenance
    source_kind: str | None = None,
    source_path: str | None = None,
    collected_at: str | None = None,
    instrument: str | None = None,
    operator: str | None = None,
    run_id: str | None = None,
    tags_json: str | None = None,
    notes: str | None = None,
) -> StoredFile:
    """Persist a file to disk + create StoredFile row.

    Deduplicates on sha256: if the file contents already exist on disk, we reuse the same
    stored_name pattern but still create a new DB row (matching MVP behavior).
    """

    sha = sha256_fileobj(data)
    safe = safe_filename(filename)
    stored_name = f"{sha[:16]}_{safe}"

    path = cfg.uploads_dir / stored_name
    if not path.exists():
        path.write_bytes(data)

    from datetime import datetime

    def _parse_iso_dt(val: str | None):
        if not val:
            return None
        s = str(val).strip()
        if not s:
            return None
        # Accept 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM[:SS]'
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    f = StoredFile(
        stored_name=stored_name,
        original_name=filename,
        size_bytes=len(data),
        mime=content_type or "application/octet-stream",
        sha256=sha,
        source_kind=(source_kind or "upload"),
        source_path=(source_path or None),
        collected_at=_parse_iso_dt(collected_at),
        imported_at=now_utc(),
        instrument=(instrument or None),
        operator=(operator or None),
        run_id=(run_id or None),
        tags_json=(tags_json or None),
        notes=(notes or None),
        created_at=now_utc(),
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


def link_file(
    db: Session,
    *,
    file_id: int,
    entity_type: str,
    entity_id: int,
    role: str | None = None,
    label: str | None = None,
    reason: Optional[str] = None,
) -> FileLink:
    link = FileLink(
        file_id=file_id,
        entity_type=entity_type,
        entity_id=entity_id,
        role=(role or "other"),
        label=(label or None),
        created_at=now_utc(),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    record_audit(
        db,
        entity_type="FileLink",
        entity_id=link.id,
        action="create",
        before=None,
        after=model_to_dict(link),
        reason=reason,
    )
    db.commit()
    return link


def add_files_to_entity(
    db: Session,
    *,
    cfg: StorageConfig,
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
    """Attach multiple uploaded files.

    uploads: list of (filename, content_type, bytes)
    """

    links: list[FileLink] = []
    for filename, content_type, data in uploads:
        if not filename:
            continue
        f = save_upload(
            db,
            cfg=cfg,
            filename=filename,
            content_type=content_type,
            data=data,
            source_kind=source_kind,
            source_path=source_path,
            collected_at=collected_at,
            instrument=instrument,
            operator=operator,
            run_id=run_id,
            tags_json=tags_json,
            notes=notes,
        )
        links.append(link_file(
            db,
            file_id=f.id,
            entity_type=entity_type,
            entity_id=entity_id,
            role=role,
            label=label,
            reason=f"attach to {entity_type}",
        ))
    return links


def delete_file_link_and_cleanup(
    db: Session,
    *,
    cfg: StorageConfig,
    filelink_id: int,
) -> None:
    """Delete a FileLink and remove orphan file rows + disk content.

    Preserves MVP behavior (best-effort cleanup).
    """

    link = db.get(FileLink, filelink_id)
    if not link:
        return

    before = model_to_dict(link)
    file_id = link.file_id
    db.delete(link)
    db.commit()

    record_audit(
        db,
        entity_type="FileLink",
        entity_id=filelink_id,
        action="delete",
        before=before,
        after=None,
        reason="unlink file",
    )
    db.commit()

    remaining = db.query(FileLink).filter(FileLink.file_id == file_id).count()
    if remaining:
        return

    f = db.get(StoredFile, file_id)
    if not f:
        return

    path = cfg.uploads_dir / f.stored_name
    db.delete(f)
    db.commit()

    try:
        if path.exists():
            path.unlink()
    except Exception:
        # best-effort; DB state is still consistent
        pass


def resolve_file_path(cfg: StorageConfig, stored: StoredFile) -> Path:
    return cfg.uploads_dir / stored.stored_name
