from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy.orm import Session

from psi.core.models import PolicyUpgradeSession
from psi.core.utils import now_utc, stable_json_dumps
from psi.core.di.policy import sha256_hex_of_canonical_json
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


def _extract_ranking_delta(*, old_norm: dict[str, Any], new_norm: dict[str, Any]) -> dict[str, Any]:
    old_rank = old_norm.get("ranking_policy") if isinstance(old_norm.get("ranking_policy"), dict) else {}
    new_rank = new_norm.get("ranking_policy") if isinstance(new_norm.get("ranking_policy"), dict) else {}
    old_criteria = old_rank.get("criteria_ids") if isinstance(old_rank.get("criteria_ids"), list) else []
    new_criteria = new_rank.get("criteria_ids") if isinstance(new_rank.get("criteria_ids"), list) else []
    old_tb = old_rank.get("tie_break_contract_id")
    new_tb = new_rank.get("tie_break_contract_id")
    old_enabled = bool(old_rank.get("enabled")) if old_rank else None
    new_enabled = bool(new_rank.get("enabled")) if new_rank else None
    return {
        "enabled_flag_changes": {
            "old": old_enabled,
            "new": new_enabled,
            "changed": bool(old_enabled != new_enabled),
        },
        "tie_break_contract_changes": {
            "old": (str(old_tb) if old_tb is not None else None),
            "new": (str(new_tb) if new_tb is not None else None),
            "changed": bool(old_tb != new_tb),
        },
        "criteria_registry_changes": {
            "removed": sorted({str(x) for x in old_criteria} - {str(x) for x in new_criteria}),
            "added": sorted({str(x) for x in new_criteria} - {str(x) for x in old_criteria}),
            "unchanged": sorted({str(x) for x in old_criteria} & {str(x) for x in new_criteria}),
        },
    }


def _extract_comparability_delta(*, old_norm: dict[str, Any], new_norm: dict[str, Any]) -> dict[str, Any]:
    old_cmp = old_norm.get("comparability_policy") if isinstance(old_norm.get("comparability_policy"), dict) else {}
    new_cmp = new_norm.get("comparability_policy") if isinstance(new_norm.get("comparability_policy"), dict) else {}
    old_rule_ids = old_cmp.get("rule_ids") if isinstance(old_cmp.get("rule_ids"), list) else []
    new_rule_ids = new_cmp.get("rule_ids") if isinstance(new_cmp.get("rule_ids"), list) else []
    old_statuses = old_cmp.get("allowed_statuses") if isinstance(old_cmp.get("allowed_statuses"), list) else []
    new_statuses = new_cmp.get("allowed_statuses") if isinstance(new_cmp.get("allowed_statuses"), list) else []
    old_gate = old_cmp.get("gating_behavior_id")
    new_gate = new_cmp.get("gating_behavior_id")
    return {
        "rule_registry_changes": {
            "removed_rule_ids": sorted({str(x) for x in old_rule_ids} - {str(x) for x in new_rule_ids}),
            "added_rule_ids": sorted({str(x) for x in new_rule_ids} - {str(x) for x in old_rule_ids}),
            "unchanged_rule_ids": sorted({str(x) for x in old_rule_ids} & {str(x) for x in new_rule_ids}),
        },
        "allowed_status_changes": {
            "removed_statuses": sorted({str(x) for x in old_statuses} - {str(x) for x in new_statuses}),
            "added_statuses": sorted({str(x) for x in new_statuses} - {str(x) for x in old_statuses}),
            "unchanged_statuses": sorted({str(x) for x in old_statuses} & {str(x) for x in new_statuses}),
        },
        "gating_behavior_changes": {
            "old": (str(old_gate) if old_gate is not None else None),
            "new": (str(new_gate) if new_gate is not None else None),
            "changed": bool(old_gate != new_gate),
        },
    }


def _extract_template_catalog_delta(*, old_norm: dict[str, Any], new_norm: dict[str, Any]) -> dict[str, Any]:
    old_tpl = old_norm.get("template_catalog") if isinstance(old_norm.get("template_catalog"), dict) else {}
    new_tpl = new_norm.get("template_catalog") if isinstance(new_norm.get("template_catalog"), dict) else {}
    old_keys = old_tpl.get("template_keys") if isinstance(old_tpl.get("template_keys"), list) else []
    new_keys = new_tpl.get("template_keys") if isinstance(new_tpl.get("template_keys"), list) else []
    old_cur = old_tpl.get("current_versions") if isinstance(old_tpl.get("current_versions"), dict) else {}
    new_cur = new_tpl.get("current_versions") if isinstance(new_tpl.get("current_versions"), dict) else {}
    old_imm = old_tpl.get("immutable_versions") if isinstance(old_tpl.get("immutable_versions"), dict) else {}
    new_imm = new_tpl.get("immutable_versions") if isinstance(new_tpl.get("immutable_versions"), dict) else {}
    old_pr = old_norm.get("template_prerequisites") if isinstance(old_norm.get("template_prerequisites"), dict) else {}
    new_pr = new_norm.get("template_prerequisites") if isinstance(new_norm.get("template_prerequisites"), dict) else {}
    return {
        "template_key_changes": {
            "removed": sorted({str(x) for x in old_keys} - {str(x) for x in new_keys}),
            "added": sorted({str(x) for x in new_keys} - {str(x) for x in old_keys}),
            "unchanged": sorted({str(x) for x in old_keys} & {str(x) for x in new_keys}),
        },
        "current_version_changes": {
            "rows": [
                {"template_key": str(k), "old": old_cur.get(k), "new": new_cur.get(k), "changed": bool(old_cur.get(k) != new_cur.get(k))}
                for k in sorted(set(str(x) for x in old_cur.keys()) | set(str(x) for x in new_cur.keys()))
            ]
        },
        "immutable_version_set_changes": {
            "rows": [
                {
                    "template_key": str(k),
                    "removed": sorted({str(x) for x in (old_imm.get(k) if isinstance(old_imm.get(k), list) else [])} - {str(x) for x in (new_imm.get(k) if isinstance(new_imm.get(k), list) else [])}),
                    "added": sorted({str(x) for x in (new_imm.get(k) if isinstance(new_imm.get(k), list) else [])} - {str(x) for x in (old_imm.get(k) if isinstance(old_imm.get(k), list) else [])}),
                }
                for k in sorted(set(str(x) for x in old_imm.keys()) | set(str(x) for x in new_imm.keys()))
            ]
        },
        "prerequisite_catalog_changes": {
            "old_catalog_id": old_pr.get("catalog_id"),
            "new_catalog_id": new_pr.get("catalog_id"),
            "changed": bool(old_pr.get("catalog_id") != new_pr.get("catalog_id")),
        },
    }


def _build_upgrade_delta_report(*, old_norm: dict[str, Any], new_norm: dict[str, Any], changed_keys: list[str]) -> dict[str, Any]:
    rows = [
        {
            "key": str(k),
            "old": old_norm.get(k),
            "new": new_norm.get(k),
            "changed": bool(old_norm.get(k) != new_norm.get(k)),
        }
        for k in sorted(set(old_norm) | set(new_norm))
    ]
    return {
        "schema_id": "upgrade_delta_report_v3",
        "schema_version": "v0.1",
        "header": {
            "from_policy_package_hash": sha256_hex_of_canonical_json(old_norm),
            "to_policy_package_hash": sha256_hex_of_canonical_json(new_norm),
            "changed_key_count": int(len(changed_keys)),
        },
        "executive_summary_bullets": {
            "categorical": sorted(
                {
                    "no_change" if not changed_keys else "policy_changed",
                    "reports_may_change" if changed_keys else "reports_stable",
                }
            )
        },
        "change_table": {"rows": rows},
        "appendix": {
            "changed_keys": sorted(changed_keys),
            "old_keys": sorted(old_norm.keys()),
            "new_keys": sorted(new_norm.keys()),
            "old_policy_hash": sha256_hex_of_canonical_json(old_norm),
            "new_policy_hash": sha256_hex_of_canonical_json(new_norm),
            "ranking_delta": _extract_ranking_delta(old_norm=old_norm, new_norm=new_norm),
            "comparability_delta": _extract_comparability_delta(old_norm=old_norm, new_norm=new_norm),
            "template_catalog_delta": _extract_template_catalog_delta(old_norm=old_norm, new_norm=new_norm),
        },
    }


def build_policy_diff_artifact(
    *,
    old_policy_pins: dict[str, Any],
    new_policy_pins: dict[str, Any],
    snapshot_ids: list[int] | tuple[int, ...] | None = None,
    deterministic_inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    old_norm = _sorted_pins(old_policy_pins or {})
    new_norm = _sorted_pins(new_policy_pins or {})
    changed_keys = [k for k in sorted(set(old_norm) | set(new_norm)) if old_norm.get(k) != new_norm.get(k)]
    upgrade_delta_report = _build_upgrade_delta_report(old_norm=old_norm, new_norm=new_norm, changed_keys=changed_keys)
    return {
        "artifact_type": "policy_upgrade_diff_v0",
        "old_policy_pins": old_norm,
        "new_policy_pins": new_norm,
        "old_policy_package_hash": sha256_hex_of_canonical_json(old_norm),
        "new_policy_package_hash": sha256_hex_of_canonical_json(new_norm),
        "old_policy_semantics_hash": sha256_hex_of_canonical_json(old_norm),
        "new_policy_semantics_hash": sha256_hex_of_canonical_json(new_norm),
        "changed_keys": changed_keys,
        "snapshot_ids": sorted({int(x) for x in (snapshot_ids or [])}),
        "deterministic_inputs": _sorted_pins(deterministic_inputs or {}),
        "delta": _delta_surface(old_norm, new_norm),
        "upgrade_delta_report": upgrade_delta_report,
    }


def render_upgrade_delta_report_html(*, delta_payload: dict[str, Any]) -> str:
    report = delta_payload.get("upgrade_delta_report") if isinstance(delta_payload.get("upgrade_delta_report"), dict) else {}
    tdir = Path(__file__).resolve().parents[1] / "web" / "templates" / "reports"
    env = Environment(
        loader=FileSystemLoader(str(tdir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("board_upgrade_delta_v3.html")
    return str(tpl.render(report=report))


def create_policy_upgrade_session(
    db: Session,
    *,
    old_policy_pins: dict[str, Any],
    new_policy_pins: dict[str, Any],
    snapshot_ids: list[int] | tuple[int, ...] | None = None,
    deterministic_inputs: dict[str, Any] | None = None,
) -> PolicyUpgradeSession:
    old_norm = _sorted_pins(old_policy_pins)
    new_norm = _sorted_pins(new_policy_pins)
    row = PolicyUpgradeSession(
        old_policy_pins_json=stable_json_dumps(old_norm),
        new_policy_pins_json=stable_json_dumps(new_norm),
        delta_payload_json=stable_json_dumps(
            build_policy_diff_artifact(
                old_policy_pins=old_norm,
                new_policy_pins=new_norm,
                snapshot_ids=snapshot_ids,
                deterministic_inputs=deterministic_inputs,
            )
        ),
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


def verify_policy_upgrade_session(db: Session, *, session_id: int) -> dict[str, Any]:
    row = db.get(PolicyUpgradeSession, int(session_id))
    if row is None:
        raise KeyError("PolicyUpgradeSession not found")
    try:
        delta = json.loads(row.delta_payload_json or "{}")
    except Exception as exc:
        raise ValueError("policy_upgrade_session_invalid_delta_payload") from exc
    if not isinstance(delta, dict):
        raise ValueError("policy_upgrade_session_invalid_delta_payload")
    snapshot_ids = delta.get("snapshot_ids") if isinstance(delta.get("snapshot_ids"), list) else []
    if not snapshot_ids:
        raise ValueError("policy_upgrade_session_missing_snapshot_set")
    deterministic_inputs = delta.get("deterministic_inputs") if isinstance(delta.get("deterministic_inputs"), dict) else {}
    if not deterministic_inputs:
        raise ValueError("policy_upgrade_session_missing_deterministic_inputs")
    return {
        "session_id": int(row.id),
        "snapshot_ids": [int(x) for x in snapshot_ids],
        "deterministic_inputs": _sorted_pins(deterministic_inputs),
        "verified": True,
    }


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
        try:
            delta_payload = json.loads(row.delta_payload_json or "{}")
        except Exception:
            delta_payload = {}
        affects_current = (not current_norm) or (new_pins == current_norm)
        if not affects_current:
            continue
        changed_keys = delta_payload.get("changed_keys") if isinstance(delta_payload.get("changed_keys"), list) else []
        semantic = bool(changed_keys)
        out.append(
            {
                "warning_code": "policy_upgrade_unacknowledged",
                "message": "policy upgrade session is unacknowledged and may affect current report pins",
                "session_id": int(row.id),
                "action_required": bool(semantic),
                "action_label": ("Action Required" if semantic else "Notice"),
                "created_at": (row.created_at.isoformat() if row.created_at else None),
                "old_policy_pin_keys": sorted(old_pins.keys()),
                "new_policy_pin_keys": sorted(new_pins.keys()),
                "semantic_delta_changed_keys": sorted(str(x) for x in changed_keys),
            }
        )
    return out


def require_upgrade_acknowledged_for_semantic_actions(db: Session, *, current_policy_pins: dict[str, Any] | None = None) -> None:
    warnings = get_unacknowledged_upgrade_warnings(db, current_policy_pins=current_policy_pins)
    blockers = [w for w in warnings if bool(w.get("action_required"))]
    if blockers:
        raise ValueError("policy_upgrade_action_required")


def run_semantic_action_with_ack_guard(
    db: Session,
    *,
    current_policy_pins: dict[str, Any] | None,
    action,
):
    require_upgrade_acknowledged_for_semantic_actions(db, current_policy_pins=current_policy_pins)
    return action()
