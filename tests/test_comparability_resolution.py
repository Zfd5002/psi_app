from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base
from psi.services.comparability import (
    _load_comparability_policy,
    create_comparability_assessment,
    derive_comparability_determination,
    get_effective_comparability,
    load_comparability_policy_latest,
    resolve_comparability_category,
)
from psi.services.report_engine import _map_governance_status_to_policy_status


def test_comparability_category_resolution_precedence_deterministic() -> None:
    out = resolve_comparability_category(
        statuses=["comparable", "not_comparable"],
        allowed_statuses=["comparable", "conditionally_comparable", "not_comparable"],
        missing_data=False,
    )
    assert str(out.get("resolved_status") or "") == "comparable"
    assert str(out.get("resolution_reason") or "") == "policy_precedence"


def test_comparability_category_resolution_handles_partial_data_deterministically() -> None:
    out = resolve_comparability_category(
        statuses=["comparable", "not_comparable"],
        allowed_statuses=["comparable", "conditionally_comparable", "not_comparable"],
        missing_data=True,
    )
    assert str(out.get("resolved_status") or "") == "not_comparable"
    assert str(out.get("resolution_reason") or "") == "missing_data"


def test_comparability_policy_v0_2_loads_with_deterministic_required_fields() -> None:
    pol = load_comparability_policy_latest()
    assert str(pol.get("policy_id") or "") == "comparability_policy_v0_2"
    assert str(pol.get("policy_version") or "") == "v0.2"
    allowed = pol.get("allowed_statuses") if isinstance(pol.get("allowed_statuses"), list) else []
    assert allowed == ["comparable_full", "comparable_partial", "not_comparable", "not_assessed"]
    rules = pol.get("rule_registry") if isinstance(pol.get("rule_registry"), list) else []
    assert [str((r or {}).get("id") or "") for r in rules] == [
        "rule_comparable_full",
        "rule_comparable_partial",
        "rule_not_comparable",
        "rule_not_assessed_default",
    ]


def test_comparability_determination_completeness_and_missing_inputs_downgrade() -> None:
    out = derive_comparability_determination(
        statuses=["comparable_full"],
        measurement_keys=[],
        snapshot_ids=[],
        missing_data=False,
    )
    assert str(out.get("category") or "") == "not_assessed"
    assert str(out.get("rule_id") or "") == "policy_inputs_missing"
    assert isinstance(out.get("measurement_keys"), list)
    assert isinstance(out.get("snapshot_ids"), list)
    missing = out.get("missing_inputs") if isinstance(out.get("missing_inputs"), dict) else {}
    assert "required_measurement_keys_missing" in missing
    assert "required_snapshot_roles_missing" in missing


def test_comparability_determination_deterministic_for_same_inputs() -> None:
    kwargs = {
        "statuses": ["not_comparable", "comparable_partial", "not_comparable"],
        "measurement_keys": ["ec50", "kd", "ec50"],
        "snapshot_ids": [2, 1, 1],
        "missing_data": False,
    }
    a = derive_comparability_determination(**kwargs)
    b = derive_comparability_determination(**kwargs)
    assert a == b


def test_governance_status_mapping_keeps_conditional_as_partial() -> None:
    assert _map_governance_status_to_policy_status("conditionally_comparable") == "comparable_partial"
    assert _map_governance_status_to_policy_status("comparable") == "comparable_full"


def test_comparability_active_loader_matches_latest_policy_version() -> None:
    active = _load_comparability_policy()
    latest = load_comparability_policy_latest()
    assert str(active.get("policy_id") or "") == str(latest.get("policy_id") or "")
    assert str(active.get("policy_version") or "") == str(latest.get("policy_version") or "")


def test_create_assessment_uses_latest_policy_and_legacy_aliases() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    db = SessionTmp()
    try:
        row = create_comparability_assessment(
            db,
            left_scope_type="molecule",
            left_scope_id=1,
            right_scope_type="molecule",
            right_scope_id=2,
            status="comparable",
            rule_id="placeholder_not_assessed",
            cited_measurement_keys=["kd"],
            cited_snapshot_ids=[1],
            as_of=datetime(2026, 2, 26, 0, 0, 0),
        )
        latest = load_comparability_policy_latest()
        assert str(row.status) == "comparable_full"
        assert str(row.rule_id) == "rule_not_assessed_default"
        assert str(row.policy_id) == str(latest.get("policy_id") or "")
        assert str(row.policy_version) == str(latest.get("policy_version") or "")
    finally:
        db.close()
        eng.dispose()


def test_effective_comparability_uses_latest_policy_order_and_statuses() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    db = SessionTmp()
    try:
        create_comparability_assessment(
            db,
            left_scope_type="molecule",
            left_scope_id=1,
            right_scope_type="molecule",
            right_scope_id=2,
            status="comparable",
            rule_id="placeholder_not_assessed",
            cited_measurement_keys=["kd"],
            cited_snapshot_ids=[1],
            as_of=datetime(2026, 2, 26, 0, 0, 0),
        )
        create_comparability_assessment(
            db,
            left_scope_type="molecule",
            left_scope_id=1,
            right_scope_type="molecule",
            right_scope_id=2,
            status="not_comparable",
            rule_id="placeholder_not_assessed",
            cited_measurement_keys=["kd"],
            cited_snapshot_ids=[1],
            as_of=datetime(2026, 2, 27, 0, 0, 0),
            allow_conflict_override=True,
        )
        out = get_effective_comparability(
            db,
            left_scope_type="molecule",
            left_scope_id=1,
            right_scope_type="molecule",
            right_scope_id=2,
            rule_id="placeholder_not_assessed",
        )
        res = out.get("category_resolution") if isinstance(out.get("category_resolution"), dict) else {}
        latest = load_comparability_policy_latest()
        allowed = [str(x).strip().lower() for x in (latest.get("allowed_statuses") or []) if str(x).strip()]
        assert res.get("allowed_statuses") == allowed
    finally:
        db.close()
        eng.dispose()
