from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from pathlib import Path

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from psi.core.models import ComparabilityAssessment
from psi.core.utils import now_utc, stable_json_dumps
from psi.core.di.policy import sha256_hex_of_canonical_json
from psi.services.attribution import record_attribution_event

_COMPARABILITY_POLICY_CACHE: dict[str, Any] | None = None


def _load_comparability_policy() -> dict[str, Any]:
    global _COMPARABILITY_POLICY_CACHE
    if isinstance(_COMPARABILITY_POLICY_CACHE, dict):
        return _COMPARABILITY_POLICY_CACHE
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / "comparability_policy_v0_1.json"
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("comparability_policy_load_error") from exc
    if not isinstance(raw, dict):
        raise ValueError("comparability_policy_load_error")
    _COMPARABILITY_POLICY_CACHE = raw
    return _COMPARABILITY_POLICY_CACHE


def _canonical_pair(
    *,
    left_scope_type: str,
    left_scope_id: int,
    right_scope_type: str,
    right_scope_id: int,
) -> tuple[str, int, str, int]:
    left = (str(left_scope_type).strip().lower(), int(left_scope_id))
    right = (str(right_scope_type).strip().lower(), int(right_scope_id))
    if left <= right:
        return left[0], left[1], right[0], right[1]
    return right[0], right[1], left[0], left[1]


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


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
    allow_conflict_override: bool = False,
) -> ComparabilityAssessment:
    pol = _load_comparability_policy()
    status_norm = str(status or "").strip().lower()
    allowed_statuses = [str(x).strip().lower() for x in (pol.get("allowed_statuses") or []) if str(x).strip()]
    if status_norm not in allowed_statuses:
        raise ValueError("comparability_unknown_status")
    rules = pol.get("rule_registry") if isinstance(pol.get("rule_registry"), list) else []
    rule_obj = next((r for r in rules if isinstance(r, dict) and str(r.get("rule_id") or "") == str(rule_id)), None)
    if rule_obj is None:
        raise ValueError("comparability_unknown_rule_id")
    l_type, l_id, r_type, r_id = _canonical_pair(
        left_scope_type=left_scope_type,
        left_scope_id=left_scope_id,
        right_scope_type=right_scope_type,
        right_scope_id=right_scope_id,
    )
    pair_key = f"{l_type}:{r_type}"
    scope_pairs = [str(x).strip().lower() for x in (rule_obj.get("scope_pairs") or []) if str(x).strip()]
    if scope_pairs and pair_key not in scope_pairs:
        raise ValueError("comparability_rule_scope_mismatch")
    keys = sorted({str(k) for k in (cited_measurement_keys or []) if str(k)})
    snaps = sorted({int(s) for s in (cited_snapshot_ids or [])})
    existing = (
        db.query(ComparabilityAssessment)
        .filter(ComparabilityAssessment.left_scope_type == l_type)
        .filter(ComparabilityAssessment.left_scope_id == l_id)
        .filter(ComparabilityAssessment.right_scope_type == r_type)
        .filter(ComparabilityAssessment.right_scope_id == r_id)
        .filter(ComparabilityAssessment.rule_id == str(rule_id))
        .filter(ComparabilityAssessment.as_of == as_of)
        .order_by(ComparabilityAssessment.id.asc())
        .all()
    )
    if existing:
        statuses = sorted({str(r.status or "") for r in existing})
        if status_norm in statuses:
            raise ValueError("comparability_duplicate_same_pair_rule_asof")
        if not allow_conflict_override:
            raise ValueError("comparability_conflict_same_pair_rule_asof")
    row = ComparabilityAssessment(
        left_scope_type=l_type,
        left_scope_id=l_id,
        right_scope_type=r_type,
        right_scope_id=r_id,
        status=status_norm,
        rule_id=str(rule_id),
        cited_measurement_keys_json=_stable_json(keys),
        cited_snapshot_ids_json=_stable_json(snaps),
        as_of=as_of,
        policy_id=str(policy_id),
        policy_version=str(policy_version),
        policy_package_hash=(str(policy_package_hash) if policy_package_hash else None),
        policy_semantics_hash=sha256_hex_of_canonical_json(pol),
        created_at=now_utc(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    record_attribution_event(
        db,
        event_type="comparability.assessment.create",
        entity_type="ComparabilityAssessment",
        entity_id=int(row.id),
        metadata={
            "left_scope_type": str(row.left_scope_type),
            "left_scope_id": int(row.left_scope_id),
            "right_scope_type": str(row.right_scope_type),
            "right_scope_id": int(row.right_scope_id),
            "status": str(row.status),
            "rule_id": str(row.rule_id),
            "as_of": (row.as_of.isoformat() if row.as_of else None),
            "policy_id": str(row.policy_id),
            "policy_version": str(row.policy_version),
        },
    )
    db.commit()
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
                "policy_semantics_hash": (str(r.policy_semantics_hash) if r.policy_semantics_hash else None),
            }
        )
    return out


def get_effective_comparability(
    db: Session,
    *,
    left_scope_type: str,
    left_scope_id: int,
    right_scope_type: str,
    right_scope_id: int,
    rule_id: str | None = None,
) -> dict[str, Any]:
    l_type, l_id, r_type, r_id = _canonical_pair(
        left_scope_type=left_scope_type,
        left_scope_id=left_scope_id,
        right_scope_type=right_scope_type,
        right_scope_id=right_scope_id,
    )
    q = (
        db.query(ComparabilityAssessment)
        .filter(ComparabilityAssessment.left_scope_type == l_type)
        .filter(ComparabilityAssessment.left_scope_id == l_id)
        .filter(ComparabilityAssessment.right_scope_type == r_type)
        .filter(ComparabilityAssessment.right_scope_id == r_id)
    )
    if str(rule_id or "").strip():
        q = q.filter(ComparabilityAssessment.rule_id == str(rule_id))
    rows = q.order_by(ComparabilityAssessment.as_of.desc(), ComparabilityAssessment.id.desc()).all()
    if not rows:
        return {
            "effective": None,
            "history_summary": {},
            "governance_warnings": [],
            "canonical_pair": {"left_scope_type": l_type, "left_scope_id": l_id, "right_scope_type": r_type, "right_scope_id": r_id},
        }
    effective = rows[0]
    summary: dict[str, int] = {}
    for r in rows:
        k = str(r.status or "")
        summary[k] = summary.get(k, 0) + 1
    warnings: list[dict[str, Any]] = []
    # legacy guard: multiple rows same (as_of, rule_id)
    by_asof_rule: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        key = ((r.as_of.isoformat() if r.as_of else ""), str(r.rule_id or ""))
        by_asof_rule.setdefault(key, []).append(int(r.id))
    for (as_of_iso, rid), ids in sorted(by_asof_rule.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if len(ids) > 1:
            warnings.append(
                {
                    "warning_code": "multiple_entries_same_asof_rule",
                    "as_of": as_of_iso,
                    "rule_id": rid,
                    "ids": sorted(ids),
                }
            )
    rule_ids = sorted({str(r.rule_id or "") for r in rows})
    if len(rule_ids) > 1:
        warnings.append(
            {
                "warning_code": "multiple_rule_ids_present",
                "rule_ids": rule_ids,
            }
        )
    return {
        "effective": {
            "id": int(effective.id),
            "status": str(effective.status),
            "rule_id": str(effective.rule_id),
            "as_of": (effective.as_of.isoformat() if effective.as_of else None),
            "policy_version": str(effective.policy_version),
            "policy_package_hash": (str(effective.policy_package_hash) if effective.policy_package_hash else None),
            "policy_semantics_hash": (str(effective.policy_semantics_hash) if effective.policy_semantics_hash else None),
        },
        "history_summary": {k: summary[k] for k in sorted(summary.keys())},
        "governance_warnings": warnings,
        "canonical_pair": {"left_scope_type": l_type, "left_scope_id": l_id, "right_scope_type": r_type, "right_scope_id": r_id},
    }
