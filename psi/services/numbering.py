from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from psi.core.antibody_numbering import number_variable_domain
from psi.core.deps import abnumber_available
from psi.core.models import DomainArtifact, DomainInstance, SequenceEntity
from psi.core.utils import now_utc
from psi.services.domain_artifacts import ensure_domain_artifact_running, set_artifact_failure, set_artifact_skipped, set_artifact_success


def _settings_hash(settings: Any) -> str:
    blob = json.dumps(settings, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return sha256(blob.encode('utf-8')).hexdigest()


def trigger_numbering_for_molecule(db: Session, *, molecule_id: int, scheme: str, force: bool = False) -> list[DomainArtifact]:
    """Compute (or recompute) numbering artifacts for all VH/VL domain_instances.

    - Gated on optional dependencies.
    - Safe to run multiple times (idempotent via deterministic keys).
    """
    scheme_l = (scheme or "kabat").lower()
    settings = {"scheme": scheme_l}
    tool_name = "abnumber"
    tool_version = "unknown"
    if abnumber_available():
        try:
            import abnumber  # type: ignore

            tool_version = getattr(abnumber, "__version__", "unknown")
        except Exception:
            tool_version = "unknown"
    else:
        tool_version = "unavailable"

    instances = db.execute(
        select(DomainInstance)
        .where(DomainInstance.molecule_id == molecule_id)
        .where(DomainInstance.domain_type.in_(["VH", "VL"]))
        .where(DomainInstance.status == "success")
    ).scalars().all()

    out: list[DomainArtifact] = []
    for inst in instances:
        if not inst.domain_sequence_id:
            continue
        art, created = ensure_domain_artifact_running(
            db,
            sequence_id=inst.domain_sequence_id,
            artifact_type="ab_numbering",
            domain_type=inst.domain_type,
            tool_name=tool_name,
            tool_version=tool_version,
            settings=settings,
        )
        out.append(art)
        if not created and not force:
            continue

        # Reset existing artifact to "running" when forcing recompute.
        if not created and force:
            art.status = "running"
            art.error = None
            art.updated_at = now_utc()
            db.add(art)
            db.commit()
            db.refresh(art)

        # Dependency gate (abnumber)
        if not abnumber_available():
            set_artifact_skipped(db, art, code="dependency_missing", reason="abnumber not installed (install requirements-heavy.txt)")
            continue

        # Compute and store
        try:
            seq = db.get(SequenceEntity, inst.domain_sequence_id)
            if not seq:
                set_artifact_failure(db, art, "Sequence entity not found")
                continue
            res = number_variable_domain(seq.sequence_norm, scheme=scheme_l)
            if not res:
                set_artifact_failure(db, art, "Numbering unavailable")
                continue

            labels = getattr(res, "labels_by_raw_index", None)
            # Avoid misleading "success" artifacts: Viewer v2 requires labels.
            if not labels or (isinstance(labels, list) and not any(bool(x) for x in labels)):
                set_artifact_failure(db, art, "Numbering produced no labels")
                continue

            payload = {
                "scheme": scheme_l,
                "chain_type": res.chain_type,
                "positions": res.positions,
                "labels_by_raw_index": labels,
                "cdrs": res.cdrs,
                "spans": res.spans,
                "warnings": res.warnings,
            }
            set_artifact_success(db, art, payload)
        except Exception as e:
            set_artifact_failure(db, art, str(e))

    return out


def get_numbering_artifacts_for_molecule(db: Session, *, molecule_id: int, scheme: str) -> dict:
    scheme_l = (scheme or "kabat").lower()
    tool_name = "abnumber"
    # tool_version varies; show latest success regardless of version/settings? We'll match by settings only.
    settings_hash = _settings_hash({"scheme": scheme_l})
    instances = db.execute(
        select(DomainInstance)
        .where(DomainInstance.molecule_id == molecule_id)
        .where(DomainInstance.domain_type.in_(["VH", "VL"]))
        .where(DomainInstance.status == "success")
    ).scalars().all()
    # Backward compatible shape: result["VH"]/result["VL"] contain the latest
    # successful payload (or None). We additionally provide artifact status and
    # skip/failure details under result["artifacts"].
    result: dict = {"VH": None, "VL": None, "pending": False, "artifacts": {}}
    for inst in instances:
        if not inst.domain_sequence_id:
            continue
        art = db.execute(
            select(DomainArtifact)
            .where(DomainArtifact.sequence_id == inst.domain_sequence_id)
            .where(DomainArtifact.artifact_type == "ab_numbering")
            .where(DomainArtifact.domain_type == inst.domain_type)
            .where(DomainArtifact.tool_name == tool_name)
            .where(DomainArtifact.settings_hash == settings_hash)
            .order_by(DomainArtifact.updated_at.desc())
        ).scalar_one_or_none()
        if not art:
            continue
        if art.status == "running":
            result["pending"] = True
        # Always store latest artifact status for UI messaging.
        meta = {"status": art.status, "updated_at": str(art.updated_at), "tool_version": art.tool_version}
        if art.error:
            meta["error"] = art.error

        parsed = None
        if art.result_json:
            try:
                parsed = json.loads(art.result_json)
            except Exception:
                parsed = art.result_json
        if parsed is not None:
            meta["result"] = parsed

        result["artifacts"][inst.domain_type] = meta

        if art.status == "success" and parsed is not None:
            result[inst.domain_type] = parsed
    return result
