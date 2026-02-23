from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy.inspection import inspect as sa_inspect

from .models import AuditEvent, File, FileLink

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = Path(os.environ.get("PSI_UPLOAD_DIR", str(BASE_DIR / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def safe_filename(name: str) -> str:
    name = os.path.basename(name)
    name = SAFE_FILENAME_RE.sub("_", name)
    return name[:180] or "file"


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_fileobj(data: bytes) -> str:
    """Back-compat helper used by the web layer."""
    return sha256_bytes(data)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def json_dumps_compact(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"), ensure_ascii=False)


def model_to_dict(obj: Any) -> Dict[str, Any]:
    """Best-effort shallow model serializer for audit logs."""
    if obj is None:
        return {}
    out: Dict[str, Any] = {}
    try:
        mapper = sa_inspect(obj).mapper
        for col in mapper.column_attrs:
            k = col.key
            try:
                v = getattr(obj, k)
            except Exception:
                continue
            if isinstance(v, (str, int, float, type(None), bool)):
                out[k] = v
            elif hasattr(v, "isoformat"):
                out[k] = v.isoformat()
        if out:
            return out
    except Exception:
        pass
    for k in dir(obj):
        if k.startswith("_"):
            continue
        if k in {"metadata", "registry", "query"}:
            continue
        try:
            v = getattr(obj, k)
        except Exception:
            continue
        # SQLAlchemy instrumentation
        if callable(v):
            continue
        if k in {"__dict__", "__weakref__"}:
            continue
        if isinstance(v, (str, int, float, type(None), bool)):
            out[k] = v
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    # Keep only common keys (avoid relationship explosion)
    allow = {
        "id",
        "program_id",
        "molecule_id",
        "batch_id",
        "name",
        "title",
        "primary_id",
        "batch_id",
        "description",
        "sequences",
        "domain",
        "data_type",
        "method",
        "evidence_type",
        "strength",
        "summary",
        "details",
        "params_json",
        "results_json",
        "run_date",
        "stored_name",
        "original_name",
        "size_bytes",
        "mime",
        "sha256",
        "decision_key",
        "rules_version",
        "inputs_json",
        "outputs_json",
        "evidence_ids_json",
        "created_at",
        "updated_at",
        "entity_type",
        "entity_id",
        "action",
        "timestamp",
        "actor",
        "before_json",
        "after_json",
        "diff_json",
        "reason",
        "file_id",
    }
    return {k: v for k, v in out.items() if k in allow}


def diff_json(before: Optional[Dict[str, Any]], after: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    before = before or {}
    after = after or {}
    changed = {}
    keys = set(before.keys()) | set(after.keys())
    for k in sorted(keys):
        if before.get(k) != after.get(k):
            changed[k] = {"before": before.get(k), "after": after.get(k)}
    return changed


def log_audit(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    before: Optional[Dict[str, Any]] = None,
    after: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    actor: str = "local-user",
) -> None:
    ev = AuditEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        before_json=json.dumps(before, default=str) if before is not None else None,
        after_json=json.dumps(after, default=str) if after is not None else None,
        reason=reason,
    )
    db.add(ev)


def store_upload_and_create_file(db: Session, original_name: str, mime: str | None, data: bytes) -> File:
    sha = sha256_bytes(data)
    safe = safe_filename(original_name)
    stored_name = f"{sha[:12]}_{safe}"
    path = UPLOAD_DIR / stored_name
    # Avoid overwriting (rare, but possible with same sha and name)
    if path.exists():
        # If same content, reuse file record if exists.
        existing = db.query(File).filter(File.sha256 == sha, File.stored_name == stored_name).first()
        if existing:
            return existing
        i = 1
        while path.exists():
            stored_name = f"{sha[:12]}_{i}_{safe}"
            path = UPLOAD_DIR / stored_name
            i += 1

    path.write_bytes(data)
    f = File(
        stored_name=stored_name,
        original_name=original_name,
        size_bytes=len(data),
        mime=mime,
        sha256=sha,
    )
    db.add(f)
    db.flush()
    return f


def link_file(db: Session, file_id: int, entity_type: str, entity_id: int) -> FileLink:
    link = FileLink(file_id=file_id, entity_type=entity_type, entity_id=entity_id)
    db.add(link)
    db.flush()
    return link


def unlink_file(db: Session, link: FileLink, *, cleanup_orphans: bool = True) -> None:
    file_id = link.file_id
    db.delete(link)
    db.flush()
    if cleanup_orphans:
        still_linked = db.query(FileLink).filter(FileLink.file_id == file_id).count()
        if still_linked == 0:
            f = db.get(File, file_id)
            if f:
                path = UPLOAD_DIR / f.stored_name
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass
                db.delete(f)
