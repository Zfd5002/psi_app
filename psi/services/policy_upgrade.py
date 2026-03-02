from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import PolicyUpgradeSession
from psi.core.utils import now_utc, stable_json_dumps
from psi.services.attribution import record_attribution_event


def _sorted_pins(pins: dict[str, Any]) -> dict[str, Any]:
    return {str(k): pins[k] for k in sorted((pins or {}).keys(), key=lambda x: str(x))}


def _delta_surface(old_pins: dict[str, Any], new_pins: dict[str, Any]) -> dict[str, Any]:
    old_norm = _sorted_pins(old_pins)
    new_norm = _sorted_pins(new_pins)
    changed_keys = [k for k in sorted(set(old_norm) | set(new_norm)) if old_norm.get(k) != new_norm.get(k)]
    template_changes = [k for k in changed_keys if ("template" in k)]
    comparability_changes = [k for k in changed_keys if ("comparability" in k)]
    ranking_changes = [k for k in changed_keys if ("ranking" in k)]
    catalog_changes = [k for k in changed_keys if ("catalog" in k)]
    return {
        "changed_policy_keys": changed_keys,
        "classification": {
            "catalog_changes": catalog_changes,
            "comparability_policy_changes": comparability_changes,
            "ranking_policy_changes": ranking_changes,
            "template_changes": template_changes,
        },
        "downstream_impact_flags": {
            "comparability_semantics_changed": ("yes" if bool(comparability_changes) else "no"),
            "ranking_semantics_changed": ("yes" if bool(ranking_changes) else "no"),
            "reports_may_change": ("yes" if bool(changed_keys) else "no"),
        },
    }


def create_policy_upgrade_session(db: Session, *, old_policy_pins: dict[str, Any], new_policy_pins: dict[str, Any]) -> PolicyUpgradeSession:
    old_norm = _sorted_pins(old_policy_pins)
    new_norm = _sorted_pins(new_policy_pins)
    row = PolicyUpgradeSession(
        old_policy_pins_json=stable_json_dumps(old_norm),
        new_policy_pins_json=stable_json_dumps(new_norm),
        delta_payload_json=stable_json_dumps(_delta_surface(old_norm, new_norm)),
        operator_acknowledged=0,
        created_at=now_utc(),
        acknowledged_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_attribution_event(
        db,
        event_type="policy_upgrade.session.create",
        entity_type="PolicyUpgradeSession",
        entity_id=int(row.id),
        metadata={
            "old_policy_pin_keys": sorted(old_norm.keys()),
            "new_policy_pin_keys": sorted(new_norm.keys()),
        },
    )
    db.commit()
    db.refresh(row)
    return row


def acknowledge_policy_upgrade_session(db: Session, *, session_id: int, acknowledged: bool) -> PolicyUpgradeSession:
    row = db.get(PolicyUpgradeSession, int(session_id))
    if row is None:
        raise KeyError("PolicyUpgradeSession not found")
    row.operator_acknowledged = 1 if bool(acknowledged) else 0
    row.acknowledged_at = now_utc() if bool(acknowledged) else None
    db.add(row)
    db.commit()
    db.refresh(row)
    record_attribution_event(
        db,
        event_type="policy_upgrade.session.acknowledge",
        entity_type="PolicyUpgradeSession",
        entity_id=int(row.id),
        metadata={
            "acknowledged": bool(acknowledged),
            "acknowledged_at": (row.acknowledged_at.isoformat() if row.acknowledged_at else None),
        },
    )
    db.commit()
    db.refresh(row)
    return row


def get_unacknowledged_upgrade_warnings(db: Session, *, current_policy_pins: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    current_norm = _sorted_pins(current_policy_pins or {})
    rows = (
        db.query(PolicyUpgradeSession)
        .filter(PolicyUpgradeSession.operator_acknowledged == 0)
        .order_by(PolicyUpgradeSession.created_at.desc(), PolicyUpgradeSession.id.desc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            old_pins = _sorted_pins(json.loads(row.old_policy_pins_json or "{}"))
        except Exception:
            old_pins = {}
        try:
            new_pins = _sorted_pins(json.loads(row.new_policy_pins_json or "{}"))
        except Exception:
            new_pins = {}
        affects_current = (not current_norm) or (new_pins == current_norm)
        if not affects_current:
            continue
        out.append(
            {
                "warning_code": "policy_upgrade_unacknowledged",
                "message": "policy upgrade session is unacknowledged and may affect current report pins",
                "session_id": int(row.id),
                "created_at": (row.created_at.isoformat() if row.created_at else None),
                "old_policy_pin_keys": sorted(old_pins.keys()),
                "new_policy_pin_keys": sorted(new_pins.keys()),
            }
        )
    return out
