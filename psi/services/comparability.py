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
_CANONICAL_COMPARABILITY_POLICY_FILE = "comparability_policy_v0_2.json"


def _load_comparability_policy() -> dict[str, Any]:
    global _COMPARABILITY_POLICY_CACHE
    if isinstance(_COMPARABILITY_POLICY_CACHE, dict):
        return _COMPARABILITY_POLICY_CACHE
    p = Path(__file__).resolve().parents[1] / "core" / "di" / "catalogs" / _CANONICAL_COMPARABILITY_POLICY_FILE
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError("comparability_policy_load_error") from exc
    _COMPARABILITY_POLICY_CACHE = _validate_comparability_policy(raw if isinstance(raw, dict) else {})
    return _COMPARABILITY_POLICY_CACHE


def _validate_comparability_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise ValueError("comparability_policy_load_error")
    if not str(policy.get("policy_id") or "").strip():
        raise ValueError("comparability_policy_load_error")
    if not str(policy.get("policy_version") or "").strip():
        raise ValueError("comparability_policy_load_error")
    allowed = policy.get("allowed_statuses")
    if not isinstance(allowed, list) or not all(str(x).strip() for x in allowed):
        raise ValueError("comparability_policy_load_error")
    rules = policy.get("rule_registry")
    if not isinstance(rules, list) or not rules:
        raise ValueError("comparability_policy_load_error")
    for r in rules:
        if not isinstance(r, dict):
            raise ValueError("comparability_policy_load_error")
        for key in ("id", "description"):
            if not str(r.get(key) or "").strip():
                raise ValueError("comparability_policy_load_error")
        for key in ("match_statuses", "required_measurement_keys", "required_snapshot_roles", "rationale_fragments"):
            val = r.get(key)
            if not isinstance(val, list):
                raise ValueError("comparability_policy_load_error")
            if key in {"match_statuses", "rationale_fragments"} and not all(str(x).strip() for x in val):
                raise ValueError("comparability_policy_load_error")
    return policy


def load_comparability_policy_latest() -> dict[str, Any]:
    return _load_comparability_policy()


def _normalize_status_to_policy(status: str) -> str:
    norm = str(status or "").strip().lower()
    mapping = {
        "comparable": "comparable_full",
        "comparable_full": "comparable_full",
        "conditionally_comparable": "comparable_partial",
        "comparable_partial": "comparable_partial",
        "not_comparable": "not_comparable",
        "not_assessed": "not_assessed",
    }
    return mapping.get(norm, norm)


def _canonical_rule_id_for_policy(*, policy: dict[str, Any], status_norm: str, rule_id: str) -> str:
    raw_rule_id = str(rule_id or "").strip()
    rules = policy.get("rule_registry") if isinstance(policy.get("rule_registry"), list) else []
    normalized_ids: list[str] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rid = str(rule.get("id") or rule.get("rule_id") or "").strip()
        if rid:
            normalized_ids.append(rid)
    if raw_rule_id in normalized_ids:
        return raw_rule_id
    if raw_rule_id == "placeholder_not_assessed":
        if "rule_not_assessed_default" in normalized_ids:
            return "rule_not_assessed_default"
        alias_by_status = {
            "comparable_full": "rule_comparable_full",
            "comparable_partial": "rule_comparable_partial",
            "not_comparable": "rule_not_comparable",
            "not_assessed": "rule_not_assessed_default",
        }
        aliased = alias_by_status.get(status_norm, "rule_not_assessed_default")
        if aliased in normalized_ids:
            return aliased
    return raw_rule_id


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


def resolve_comparability_category(
    *,
    statuses: list[str] | tuple[str, ...],
    allowed_statuses: list[str] | tuple[str, ...],
    missing_data: bool = False,
) -> dict[str, Any]:
    allowed = [str(x).strip().lower() for x in (allowed_statuses or []) if str(x).strip()]
    statuses_norm = [str(s).strip().lower() for s in (statuses or []) if str(s).strip()]
    statuses_seen: dict[str, bool] = {}
    for s in statuses_norm:
        if s not in statuses_seen:
            statuses_seen[s] = True
    if bool(missing_data):
        fallback = "not_comparable"
        return {
            "resolved_status": fallback,
            "resolution_reason": "missing_data",
            "ordered_candidates": [],
            "allowed_statuses": allowed,
        }
    valid: list[str] = []
    for s in allowed:
        if s in statuses_seen:
            valid.append(s)
    if not valid:
        fallback = "not_comparable" if "not_comparable" in allowed else (allowed[-1] if allowed else "not_comparable")
        return {
            "resolved_status": fallback,
            "resolution_reason": "no_valid_status_candidates",
            "ordered_candidates": [s for s in statuses_norm if s in statuses_seen],
            "allowed_statuses": allowed,
        }
    return {
        "resolved_status": valid[0],
        "resolution_reason": "policy_precedence",
        "ordered_candidates": valid,
        "allowed_statuses": allowed,
    }


def _normalize_str_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    out: list[str] = []
    seen: dict[str, bool] = {}
    for v in values or []:
        s = str(v).strip()
        if not s:
            continue
        if s not in seen:
            seen[s] = True
            out.append(s)
    return out


def validate_comparability_determination(det: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(det, dict):
        raise ValueError("comparability_determination_invalid")
    if not isinstance(det.get("category"), str):
        raise ValueError("comparability_determination_invalid")
    if not isinstance(det.get("rule_id"), str):
        raise ValueError("comparability_determination_invalid")
    if not isinstance(det.get("measurement_keys"), list):
        raise ValueError("comparability_determination_invalid")
    if not isinstance(det.get("snapshot_ids"), list):
        raise ValueError("comparability_determination_invalid")
    return det


def derive_comparability_determination(
    *,
    statuses: list[str] | tuple[str, ...],
    measurement_keys: list[str] | tuple[str, ...],
    snapshot_ids: list[int] | tuple[int, ...],
    missing_data: bool = False,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pol = _validate_comparability_policy(policy if isinstance(policy, dict) else load_comparability_policy_latest())
    allowed = [str(x).strip().lower() for x in (pol.get("allowed_statuses") or []) if str(x).strip()]
    category_resolution = resolve_comparability_category(statuses=statuses, allowed_statuses=allowed, missing_data=bool(missing_data))
    chosen = str(category_resolution.get("resolved_status") or "not_assessed").strip().lower()
    mk = sorted(_normalize_str_list(list(measurement_keys or [])))
    sid = sorted({int(x) for x in (snapshot_ids or []) if str(x).isdigit()})
    rules = [r for r in (pol.get("rule_registry") or []) if isinstance(r, dict)]
    selected_rule: dict[str, Any] | None = None
    for r in rules:
        match = [str(x).strip().lower() for x in (r.get("match_statuses") or []) if str(x).strip()]
        if chosen in match:
            selected_rule = r
            break
    if selected_rule is None:
        selected_rule = {
            "id": "policy_no_match",
            "required_measurement_keys": [],
            "required_snapshot_roles": [],
            "rationale_fragments": ["policy_no_match"],
        }

    req_mk = [str(x).strip() for x in (selected_rule.get("required_measurement_keys") or []) if str(x).strip()]
    req_snap_roles = [str(x).strip() for x in (selected_rule.get("required_snapshot_roles") or []) if str(x).strip()]
    missing_inputs = {
        "required_measurement_keys_missing": [k for k in req_mk if k not in mk],
        "required_snapshot_roles_missing": (sorted(req_snap_roles) if req_snap_roles and not sid else []),
    }
    has_missing = bool(missing_inputs["required_measurement_keys_missing"] or missing_inputs["required_snapshot_roles_missing"])
    if has_missing:
        out = {
            "category": "not_assessed",
            "rule_id": "policy_inputs_missing",
            "measurement_keys": mk,
            "snapshot_ids": sid,
            "rationale": "policy_inputs_missing",
            "notes": ["deterministic_downgrade_due_to_missing_inputs"],
            "missing_inputs": {
                "required_measurement_keys_missing": sorted(missing_inputs["required_measurement_keys_missing"]),
                "required_snapshot_roles_missing": sorted(missing_inputs["required_snapshot_roles_missing"]),
            },
        }
        return validate_comparability_determination(out)
    rationale_parts = [str(x).strip() for x in (selected_rule.get("rationale_fragments") or []) if str(x).strip()]
    out = {
        "category": chosen,
        "rule_id": str(selected_rule.get("id") or "policy_no_match"),
        "measurement_keys": mk,
        "snapshot_ids": sid,
        "rationale": "|".join(rationale_parts) if rationale_parts else "policy_precedence",
        "notes": sorted(set([str(category_resolution.get("resolution_reason") or "policy_precedence")])),
    }
    return validate_comparability_determination(out)


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
    policy_id: str | None = None,
    policy_version: str | None = None,
    policy_package_hash: str | None = None,
    allow_conflict_override: bool = False,
) -> ComparabilityAssessment:
    pol = _load_comparability_policy()
    status_norm = _normalize_status_to_policy(status)
    allowed_statuses = [str(x).strip().lower() for x in (pol.get("allowed_statuses") or []) if str(x).strip()]
    resolved = resolve_comparability_category(statuses=[status_norm], allowed_statuses=allowed_statuses)
    if status_norm not in allowed_statuses or str(resolved.get("resolved_status") or "") != status_norm:
        raise ValueError("comparability_unknown_status")
    rules = pol.get("rule_registry") if isinstance(pol.get("rule_registry"), list) else []
    canonical_rule_id = _canonical_rule_id_for_policy(policy=pol, status_norm=status_norm, rule_id=str(rule_id))
    rule_obj = next(
        (
            r
            for r in rules
            if isinstance(r, dict) and str(r.get("id") or r.get("rule_id") or "") == canonical_rule_id
        ),
        None,
    )
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
    if not keys:
        raise ValueError("comparability_missing_measurement_citations")
    if not snaps:
        raise ValueError("comparability_missing_snapshot_citations")
    existing = (
        db.query(ComparabilityAssessment)
        .filter(ComparabilityAssessment.left_scope_type == l_type)
        .filter(ComparabilityAssessment.left_scope_id == l_id)
        .filter(ComparabilityAssessment.right_scope_type == r_type)
        .filter(ComparabilityAssessment.right_scope_id == r_id)
        .filter(ComparabilityAssessment.rule_id == canonical_rule_id)
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
        rule_id=canonical_rule_id,
        cited_measurement_keys_json=_stable_json(keys),
        cited_snapshot_ids_json=_stable_json(snaps),
        as_of=as_of,
        policy_id=str(policy_id or pol.get("policy_id") or ""),
        policy_version=str(policy_version or pol.get("policy_version") or ""),
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
    pol = _load_comparability_policy()
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
        canonical_rule_id = _canonical_rule_id_for_policy(
            policy=pol,
            status_norm="not_assessed",
            rule_id=str(rule_id),
        )
        q = q.filter(ComparabilityAssessment.rule_id == canonical_rule_id)
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
        "category_resolution": resolve_comparability_category(
            statuses=[_normalize_status_to_policy(str(r.status or "")) for r in rows],
            allowed_statuses=[str(x).strip().lower() for x in ((pol.get("allowed_statuses") or [])) if str(x).strip()],
            missing_data=False,
        ),
        "history_summary": {k: summary[k] for k in sorted(summary.keys())},
        "governance_warnings": warnings,
        "canonical_pair": {"left_scope_type": l_type, "left_scope_id": l_id, "right_scope_type": r_type, "right_scope_id": r_id},
    }
