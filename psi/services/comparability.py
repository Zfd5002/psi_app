from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from psi.core.models import ComparabilityAssessment
from psi.core.utils import now_utc, stable_json_dumps

ALLOWED_COMPARABILITY_STATUSES = (
    "comparable",
    "conditionally_comparable",
    "not_comparable",
)


def create_comparability_assessment(
    db: Session,
    *,
    left_scope_type: str,
    left_scope_id: int,
    right_scope_type: str,
    right_scope_id: int,
    status: str,
    rule_id: str,
    cited_measurement_keys: list[str],
    cited_snapshot_ids: list[int],
    as_of: datetime,
    policy_id: str = "comparability_policy_v0_1",
    policy_version: str = "v0.1",
    policy_package_hash: str | None = None,
) -> ComparabilityAssessment:
    status_norm = str(status or "").strip().lower()
    if status_norm not in ALLOWED_COMPARABILITY_STATUSES:
        raise ValueError("Invalid comparability status")
    keys = sorted({str(k) for k in (cited_measurement_keys or []) if str(k)})
    snaps = sorted({int(s) for s in (cited_snapshot_ids or [])})
    row = ComparabilityAssessment(
        left_scope_type=str(left_scope_type),
        left_scope_id=int(left_scope_id),
        right_scope_type=str(right_scope_type),
        right_scope_id=int(right_scope_id),
        status=status_norm,
        rule_id=str(rule_id),
        cited_measurement_keys_json=stable_json_dumps(keys),
        cited_snapshot_ids_json=stable_json_dumps(snaps),
        as_of=as_of,
        policy_id=str(policy_id),
        policy_version=str(policy_version),
        policy_package_hash=(str(policy_package_hash) if policy_package_hash else None),
        created_at=now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_comparability_assessments(db: Session, *, scope_type: str, scope_id: int) -> list[dict]:
    rows = (
        db.query(ComparabilityAssessment)
        .filter(
            or_(
                and_(ComparabilityAssessment.left_scope_type == scope_type, ComparabilityAssessment.left_scope_id == scope_id),
                and_(ComparabilityAssessment.right_scope_type == scope_type, ComparabilityAssessment.right_scope_id == scope_id),
            )
        )
        .order_by(ComparabilityAssessment.as_of.desc(), ComparabilityAssessment.id.desc())
        .all()
    )
    out: list[dict] = []
    for r in rows:
        try:
            keys = json.loads(r.cited_measurement_keys_json or "[]")
        except Exception:
            keys = []
        try:
            snaps = json.loads(r.cited_snapshot_ids_json or "[]")
        except Exception:
            snaps = []
        out.append(
            {
                "id": int(r.id),
                "left_scope_type": str(r.left_scope_type),
                "left_scope_id": int(r.left_scope_id),
                "right_scope_type": str(r.right_scope_type),
                "right_scope_id": int(r.right_scope_id),
                "status": str(r.status),
                "rule_id": str(r.rule_id),
                "cited_measurement_keys": sorted(str(k) for k in keys if str(k)),
                "cited_snapshot_ids": sorted(int(s) for s in snaps if isinstance(s, int)),
                "as_of": r.as_of.isoformat() if r.as_of is not None else None,
                "policy_id": str(r.policy_id),
                "policy_version": str(r.policy_version),
                "policy_package_hash": (str(r.policy_package_hash) if r.policy_package_hash else None),
            }
        )
    return out
