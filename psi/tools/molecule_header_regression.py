from __future__ import annotations

import sys


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_moderate_normalizes_to_medium() -> None:
    from psi.services.molecule_header import _build_header_risk_items

    items = _build_header_risk_items(
        latest_di_row={"_out": {"risk_flags_enriched": [{"key": "x_flag", "severity": "moderate"}]}}
    )
    _assert(isinstance(items, list) and len(items) == 1, "expected one header risk item")
    it = items[0] if isinstance(items[0], dict) else {}
    _assert(str(it.get("severity") or "") == "medium", "moderate severity must normalize to medium")


def test_two_medium_concerns_yield_amber_scalar() -> None:
    from psi.services.molecule_header import _derive_confidence_scalar_from_components

    state, label, counts = _derive_confidence_scalar_from_components(
        components=[
            {"key": "qc_quality", "state": "concern", "severity": "medium"},
            {"key": "comparability", "state": "concern", "severity": "medium"},
            {"key": "reproducibility", "state": "not_assessed"},
            {"key": "interpretability", "state": "good"},
        ]
    )
    _assert(state == "amber", "two medium concerns must yield amber")
    _assert("Multiple Medium" in str(label or ""), "amber scalar label should explain multiple medium concerns")
    _assert(int((counts or {}).get("medium_concerns") or 0) == 2, "medium concern count must be deterministic")


def test_missing_assays_neutral_invariant() -> None:
    from psi.services.molecule_header import _build_confidence_model

    cm = _build_confidence_model(
        latest_di_row={"_out": {"gates": []}},
        risk_severity_counts={"high": 0, "medium": 0, "low": 0, "unspecified": 0},
    )
    comps = cm.get("components") if isinstance(cm, dict) else []
    by_key = {str((c or {}).get("key") or ""): (c or {}) for c in comps if isinstance(c, dict)}
    _assert(str((by_key.get("qc_quality") or {}).get("state") or "") == "not_assessed", "missing QC evidence must remain neutral")
    _assert(str((by_key.get("reproducibility") or {}).get("state") or "") == "not_assessed", "missing reproducibility evidence must remain neutral")
    _assert(str((by_key.get("comparability") or {}).get("state") or "") == "not_assessed", "missing comparability evidence must remain neutral")
    _assert(str((by_key.get("interpretability") or {}).get("state") or "") == "good", "no risk flags should not penalize interpretability")


def main() -> int:
    try:
        test_moderate_normalizes_to_medium()
        test_two_medium_concerns_yield_amber_scalar()
        test_missing_assays_neutral_invariant()
    except Exception as exc:
        print(f"molecule_header_regression FAILED: {exc}", file=sys.stderr)
        return 1
    print("molecule_header_regression OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
