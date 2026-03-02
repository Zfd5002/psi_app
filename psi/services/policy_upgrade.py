from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import PolicyUpgradeSession
from psi.core.utils import now_utc, stable_json_dumps


def _sorted_pins(pins: dict[str, Any]) -> dict[str, Any]:
    return {str(k): pins[k] for k in sorted((pins or {}).keys(), key=lambda x: str(x))}


def _delta_surface(old_pins: dict[str, Any], new_pins: dict[str, Any]) -> dict[str, Any]:
    old_norm = _sorted_pins(old_pins)
    new_norm = _sorted_pins(new_pins)
    changed_keys = [k for k in sorted(set(old_norm) | set(new_norm)) if old_norm.get(k) != new_norm.get(k)]
    return {
        "ranking_deltas": {"status": "not_assessed", "changed_policy_keys": [k for k in changed_keys if "ranking" in k]},
        "comparability_deltas": {"status": "not_assessed", "changed_policy_keys": [k for k in changed_keys if "comparability" in k]},
        "report_section_deltas": {"status": "not_assessed", "changed_policy_keys": changed_keys},
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
    return row
