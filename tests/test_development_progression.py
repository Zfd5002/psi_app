from __future__ import annotations

from psi.services import development_progression as dp


def test_progression_summary_orders_gates_and_reports_blocking_stage() -> None:
    out = dp.build_progression_summary(
        {
            "decision_state": "not_ready",
            "gates": [
                {"gate_key": "G1_material_readiness"},
                {"gate_key": "G2_purity_integrity"},
                {"gate_key": "G3_endotoxin"},
            ],
            "gate_outcomes": {
                "G1_material_readiness": {"status": "pass", "missing": [], "failed_metrics": []},
                "G2_purity_integrity": {"status": "pass", "missing": [], "failed_metrics": []},
                "G3_endotoxin": {"status": "fail", "missing": [], "failed_metrics": ["value_eu_ml"]},
            },
            "recommended_experiments": [{"metric_key": "value_eu_ml"}],
        }
    )
    assert out["decision_label"] == "Development Progression"
    assert out["current_stage_label"] == "Gate 3: Endotoxin Control"
    assert out["blocking_stage_label"] == "Gate 3: Endotoxin Control"
    assert out["passed_stage_labels"] == ["Gate 1: Material Readiness", "Gate 2: Quality / Integrity"]
    assert out["failing_requirement_labels"] == ["Value Eu Ml"]
    assert "Run assay for Value Eu Ml." == out["recommended_next_step"]


def test_progression_summary_handles_not_assessed_deterministically() -> None:
    out = dp.build_progression_summary({})
    assert out["overall_status"] == "not_assessed"
    assert out["current_stage_label"] == "Not assessed"
    assert out["stages"] == []
