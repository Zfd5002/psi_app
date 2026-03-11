from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from psi.core.constant_regions import analyze_constant_regions
from psi.core.models import DomainArtifact, MoleculeComponent
from psi.services.domain_artifacts import ensure_domain_artifact_running, set_artifact_failure, set_artifact_success


_ARTIFACT_TYPE = "constant_region_annotations"
_TOOL_NAME = "psi_constant_regions"
_TOOL_VERSION = "d138"


def _settings() -> dict[str, Any]:
    return {"pipeline": _ARTIFACT_TYPE, "analysis_version": _TOOL_VERSION}


def _safe_parse_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        val = json.loads(raw)
    except Exception:
        return None
    return val if isinstance(val, dict) else None


def _load_existing_artifact(
    db: Session,
    *,
    sequence_id: int,
) -> DomainArtifact | None:
    settings = _settings()
    # Hashing logic is inside ensure_domain_artifact_running; we query latest for tool/version.
    rows = (
        db.execute(
            select(DomainArtifact)
            .where(DomainArtifact.sequence_id == int(sequence_id))
            .where(DomainArtifact.artifact_type == _ARTIFACT_TYPE)
            .where(DomainArtifact.domain_type.is_(None))
            .where(DomainArtifact.tool_name == _TOOL_NAME)
            .where(DomainArtifact.tool_version == _TOOL_VERSION)
            .order_by(DomainArtifact.updated_at.desc(), DomainArtifact.id.desc())
        )
        .scalars()
        .all()
    )
    if not rows:
        return None

    # Keep first row matching current settings hash if present.
    target = rows[0]
    for art in rows:
        if art.settings_hash == target.settings_hash:
            return art
    return target


def _ensure_constant_artifact_for_sequence(
    db: Session,
    *,
    sequence_id: int,
    seq: str,
) -> dict[str, Any]:
    existing = _load_existing_artifact(db, sequence_id=int(sequence_id))
    if existing and existing.status == "success":
        parsed = _safe_parse_json(existing.result_json)
        if isinstance(parsed, dict):
            return parsed

    art, created = ensure_domain_artifact_running(
        db,
        sequence_id=int(sequence_id),
        artifact_type=_ARTIFACT_TYPE,
        domain_type=None,
        tool_name=_TOOL_NAME,
        tool_version=_TOOL_VERSION,
        settings=_settings(),
    )

    if not created and art.status == "success":
        parsed = _safe_parse_json(art.result_json)
        if isinstance(parsed, dict):
            return parsed

    try:
        payload = analyze_constant_regions(seq=seq)
        set_artifact_success(db, art, payload)
        return payload
    except Exception as e:
        set_artifact_failure(db, art, str(e))
        return {"analysis_version": _TOOL_VERSION, "features": [], "error": str(e)}


def get_constant_region_payload_for_components(
    db: Session,
    *,
    components: list[MoleculeComponent],
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for c in list(components or []):
        comp_id = int(getattr(c, "id", 0) or 0)
        if not comp_id:
            continue
        seq = str(getattr(c, "fasta", "") or "")
        if not seq:
            out[comp_id] = {"analysis_version": _TOOL_VERSION, "features": []}
            continue
        seq_id = int(getattr(c, "sequence_entity_id", 0) or 0)
        if seq_id > 0:
            out[comp_id] = _ensure_constant_artifact_for_sequence(db, sequence_id=seq_id, seq=seq)
        else:
            out[comp_id] = analyze_constant_regions(seq=seq)
    return out
