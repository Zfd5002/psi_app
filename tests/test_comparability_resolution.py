from __future__ import annotations

from psi.services.comparability import (
    derive_comparability_determination,
    load_comparability_policy_latest,
    resolve_comparability_category,
)


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
