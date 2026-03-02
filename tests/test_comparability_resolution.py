from __future__ import annotations

from psi.services.comparability import resolve_comparability_category


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

