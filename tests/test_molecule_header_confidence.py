from psi.services.molecule_header import (
    _build_confidence_model,
    _build_header_risk_items,
    _derive_confidence_scalar_from_components,
)


def test_moderate_severity_normalizes_to_medium_in_header_items():
    items = _build_header_risk_items(
        latest_di_row={"_out": {"risk_flags_enriched": [{"key": "rf_x", "severity": "moderate"}]}}
    )
    assert len(items) == 1
    assert items[0]["severity"] == "medium"


def test_two_medium_concerns_produce_amber_scalar():
    state, label, counts = _derive_confidence_scalar_from_components(
        components=[
            {"key": "qc_quality", "state": "concern", "severity": "medium"},
            {"key": "comparability", "state": "concern", "severity": "medium"},
            {"key": "reproducibility", "state": "good"},
            {"key": "interpretability", "state": "not_assessed"},
        ]
    )
    assert state == "amber"
    assert "Multiple Medium" in label
    assert counts["medium_concerns"] == 2


def test_missing_assays_remain_neutral_not_assessed():
    cm = _build_confidence_model(
        latest_di_row={"_out": {"gates": []}},
        risk_severity_counts={"high": 0, "medium": 0, "low": 0, "unspecified": 0},
    )
    comps = {c["key"]: c for c in cm["components"]}
    assert comps["qc_quality"]["state"] == "not_assessed"
    assert comps["reproducibility"]["state"] == "not_assessed"
    assert comps["comparability"]["state"] == "not_assessed"
    assert comps["interpretability"]["state"] == "good"
