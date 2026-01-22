from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.models import DomainArtifact, SequenceEntity
from psi.core.utils import now_utc


def _stable_settings_hash(obj: Any) -> str:
    """Hash arbitrary settings deterministically."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(blob.encode("utf-8")).hexdigest()


def get_sequence_entity(db: Session, sequence_id: int) -> Optional[SequenceEntity]:
    return db.get(SequenceEntity, sequence_id)


def get_domain_artifact(
    db: Session,
    *,
    sequence_id: int,
    artifact_type: str,
    domain_type: str | None,
    tool_name: str,
    tool_version: str,
    settings_hash: str,
) -> Optional[DomainArtifact]:
    stmt = (
        select(DomainArtifact)
        .where(DomainArtifact.sequence_id == sequence_id)
        .where(DomainArtifact.artifact_type == artifact_type)
        .where(DomainArtifact.domain_type == domain_type)
        .where(DomainArtifact.tool_name == tool_name)
        .where(DomainArtifact.tool_version == tool_version)
        .where(DomainArtifact.settings_hash == settings_hash)
    )
    return db.execute(stmt).scalar_one_or_none()


def ensure_domain_artifact_running(
    db: Session,
    *,
    sequence_id: int,
    artifact_type: str,
    domain_type: str | None,
    tool_name: str,
    tool_version: str,
    settings: Any,
) -> tuple[DomainArtifact, bool]:
    """Get existing artifact or create a new 'running' record.

    Returns (artifact, created_new).
    """
    settings_hash = _stable_settings_hash(settings)
    existing = get_domain_artifact(
        db,
        sequence_id=sequence_id,
        artifact_type=artifact_type,
        domain_type=domain_type,
        tool_name=tool_name,
        tool_version=tool_version,
        settings_hash=settings_hash,
    )
    if existing:
        return existing, False

    art = DomainArtifact(
        sequence_id=sequence_id,
        artifact_type=artifact_type,
        domain_type=domain_type,
        tool_name=tool_name,
        tool_version=tool_version,
        settings_hash=settings_hash,
        status="running",
        result_json=None,
        error=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(art)
    try:
        db.commit()
        db.refresh(art)
        return art, True
    except IntegrityError:
        db.rollback()
        # Someone else created it; return the winner.
        existing2 = get_domain_artifact(
            db,
            sequence_id=sequence_id,
            artifact_type=artifact_type,
            domain_type=domain_type,
            tool_name=tool_name,
            tool_version=tool_version,
            settings_hash=settings_hash,
        )
        if existing2:
            return existing2, False
        raise


def set_artifact_success(db: Session, art: DomainArtifact, result: Any) -> DomainArtifact:
    art.status = "success"
    art.result_json = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    art.error = None
    art.updated_at = now_utc()
    db.add(art)
    db.commit()
    db.refresh(art)
    return art


def set_artifact_failure(db: Session, art: DomainArtifact, error: str) -> DomainArtifact:
    art.status = "failure"
    art.error = error
    art.updated_at = now_utc()
    db.add(art)
    db.commit()
    db.refresh(art)
    return art


def set_artifact_skipped(db: Session, art: DomainArtifact, *, code: str, reason: str, extra: dict | None = None) -> DomainArtifact:
    """Mark an artifact as skipped.

    We treat "skipped" as a first-class status without introducing schema
    changes (status is stored as free text).
    """
    payload = {"skipped": True, "code": code, "reason": reason}
    if extra:
        payload["extra"] = extra

    art.status = "skipped"
    art.result_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    art.error = None
    art.updated_at = now_utc()
    db.add(art)
    db.commit()
    db.refresh(art)
    return art
