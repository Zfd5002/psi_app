from __future__ import annotations

from psi.services.insight_engine import (
    build_insight_bundle,
    extract_policy_expectations,
    generate_decision_summary,
    summarize_trend_signals,
)


def test_build_insight_bundle_extracts_missing_and_failing_metrics_deterministically() -> None:
    snap = {
        "decision_state": "not_ready",
        "gate_outcomes": {
            "G2": {"status": "fail", "missing": ["kd"], "failed_metrics": ["ec50"]},
            "G1": {"status": "pass", "missing": [], "failed_metrics": []},
        },
        "blockers": [
            {"blocker_key": "missing_required_metric", "detail": {"gate": "G2", "missing": ["kd"]}},
        ],
    }
    out = build_insight_bundle(snap)
    assert out["molecule_status"] == "not_ready"
    assert [x["metric_key"] for x in out["missing_evidence"]] == ["kd"]
    assert out["missing_evidence"][0]["classification"] == "missing"
    assert [x["metric_key"] for x in out["failing_evidence"]] == ["ec50"]
    assert [x["metric_key"] for x in out["recommended_experiments"]] == ["kd", "ec50"]
    assert [x["priority"] for x in out["recommended_experiments"]] == [1, 2]


def test_build_insight_bundle_handles_nested_output_shape() -> None:
    snap = {
        "output": {
            "decision_state": "ready",
            "gate_outcomes": {},
            "blockers": [],
        }
    }
    out = build_insight_bundle(snap)
    assert out["molecule_status"] == "ready"
    assert out["blocking_issues"] == []
    assert out["missing_evidence"] == []
    assert out["failing_evidence"] == []


def test_insight_bundle_classifies_supporting_and_blocking_evidence() -> None:
    snap = {
        "decision_state": "not_ready",
        "gate_outcomes": {
            "G1": {"status": "fail", "missing": ["kd"], "failed_metrics": ["ec50"]},
        },
        "state_of_evidence": {"used": {"ec50": {"value_num": 500}, "tm_c": {"value_num": 70}}},
    }
    out = build_insight_bundle(snap)
    assert [x["metric_key"] for x in out["strongest_blocking_evidence"]] == ["ec50", "kd"]
    assert [x["metric_key"] for x in out["strongest_supporting_evidence"]] == ["tm_c"]


def test_extract_policy_expectations_reads_thresholds_and_requirements() -> None:
    policy = {
        "policy_body": {
            "gates": {
                "G1": {
                    "thresholds": {"monomer_pct": {"min_value": 85}, "kd_nM": {"max_value": 10}},
                    "require_all": ["ec50"],
                }
            }
        }
    }
    out = extract_policy_expectations(policy)
    vals = [x["expectation"] for x in out]
    assert "Monomer >= 85 %" in vals
    assert "KD <= 10 nM" in vals
    assert "EC50 required" in vals


def test_generate_decision_summary_is_plain_and_deterministic() -> None:
    bundle = {
        "molecule_status": "not_ready",
        "missing_evidence": [{"metric_key": "kd"}],
        "failing_evidence": [{"metric_key": "sec_monomer_pct"}],
    }
    s = generate_decision_summary(bundle)
    assert "Molecule status is not ready." in s
    assert "Blocked by failing evidence: sec_monomer_pct." in s
    assert "Missing required evidence: kd." in s


def test_summarize_trend_signals_classifies_direction_deterministically() -> None:
    out = summarize_trend_signals(
        {
            "series": {
                "kd_nM": [{"value": 10.0}, {"value": 8.0}],
                "monomer_pct": [{"value": 80.0}, {"value": 86.0}],
                "value_eu_ml": [{"value": 0.2}],
            }
        }
    )
    by_key = {x["metric_key"]: x for x in out}
    assert by_key["kd_nM"]["signal"] == "declining"
    assert by_key["monomer_pct"]["signal"] == "improving"
    assert by_key["value_eu_ml"]["signal"] == "stable"
