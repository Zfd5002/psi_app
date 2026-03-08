from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.services.trajectory import (
    build_trajectory_tree,
    build_program_trajectory,
    build_portfolio_trajectory,
    generate_trajectory_candidates,
    predict_gate_transitions,
    predict_metric_delta,
    predict_readiness_shift,
    rank_trajectory_candidates,
    score_trajectory_confidence,
    simulate_experiment_set,
    simulate_experiment_outcome,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_simulate_experiment_outcome_returns_expected_shape() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-traj", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-traj", title="", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            out = {
                "decision_state": "not_ready",
                "gate_outcomes": {"binding_gate": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}},
                "blockers": [],
            }
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json=json.dumps(out),
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            db.commit()

            row = simulate_experiment_outcome(
                db,
                molecule_id=int(m.id),
                metric_key="kd_nM",
                simulated_value=2.5,
            )
            assert int(row["molecule_id"]) == int(m.id)
            assert "predicted_gate_changes" in row
            assert "predicted_readiness_change" in row
            assert row["impacted_metrics"] == ["kd_nM"]
            assert row["predicted_readiness_change"]["before"] == "not_ready"
            assert row["predicted_readiness_change"]["after"] == "ready"
            assert row["confidence_level"] in {"low", "medium", "high"}
            assert 0.0 <= float(row["confidence_score"]) <= 1.0
        finally:
            db.close()
    finally:
        eng.dispose()


def test_simulate_experiment_outcome_without_snapshot_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-traj-nosnap", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-nosnap", title="", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            a = simulate_experiment_outcome(db, molecule_id=int(m.id), metric_key="sec_monomer_pct", simulated_value=95)
            b = simulate_experiment_outcome(db, molecule_id=int(m.id), metric_key="sec_monomer_pct", simulated_value=95)
            assert a == b
            assert a["predicted_readiness_change"]["before"] == "not_assessed"
            assert a["predicted_readiness_change"]["after"] == "not_assessed"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_predict_metric_delta_maps_experiment_categories_deterministically() -> None:
    a = predict_metric_delta("kd_nM", "BLI KD run")
    b = predict_metric_delta("sec_monomer_pct", "SEC-HPLC purity")
    c = predict_metric_delta("internalization_score", "internalization assay")
    d = predict_metric_delta("unknown_metric", "custom")
    assert a["impacted_metrics"] == ["kd_nM"]
    assert "hwm_pct" in b["impacted_metrics"]
    assert "sec_monomer_pct" in b["impacted_metrics"]
    assert c["impacted_metrics"] == ["internalization_score"]
    assert d["impacted_metrics"] == ["unknown_metric"]


def test_predict_gate_transitions_returns_deterministic_gate_deltas() -> None:
    changes = [{"metric_key": "kd_nM", "simulated_value": 2.0}]
    out = predict_gate_transitions(changes, gate_context={"kd_nM": ["binding_gate", "developability_gate"]})
    assert [x["gate_key"] for x in out] == ["binding_gate", "developability_gate"]
    assert all(x["gate_before"] == "fail_or_hold" for x in out)
    assert all(x["gate_after"] == "pass" for x in out)


def test_predict_readiness_shift_transitions_to_ready_when_gates_improve() -> None:
    out = predict_readiness_shift(
        [{"gate_key": "binding_gate", "delta": "improved"}],
        [{"metric_key": "kd_nM", "simulated_value": 1.1}],
        readiness_before="not_ready",
    )
    assert out["readiness_before"] == "not_ready"
    assert out["readiness_after"] == "ready"


def test_score_trajectory_confidence_deterministic_range() -> None:
    a = score_trajectory_confidence(metric_key="kd_nM", assumptions_count=0, historical_metric_stability=0.8)
    b = score_trajectory_confidence(metric_key="kd_nM", assumptions_count=2, historical_metric_stability=0.8)
    assert 0.0 <= a <= 1.0
    assert 0.0 <= b <= 1.0
    assert a > b


def test_generate_trajectory_candidates_from_recommended_experiments() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-cand", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-cand", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            out = {
                "decision_state": "not_ready",
                "gate_outcomes": {"g1": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}},
                "blockers": [],
            }
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json=json.dumps(out),
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            db.commit()
            rows = generate_trajectory_candidates(db, molecule_id=int(m.id))
            assert len(rows) >= 1
            assert rows[0]["metric_key"] == "kd_nM"
            assert "expected_readiness_gain" in rows[0]
            assert "metric_coverage_improvement" in rows[0]
            assert "gate_impact" in rows[0]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_rank_trajectory_candidates_orders_by_gain_confidence_and_effort() -> None:
    ranked = rank_trajectory_candidates(
        [
            {
                "metric_key": "sec_monomer_pct",
                "suggested_assay": "SEC-HPLC",
                "expected_readiness_gain": 1,
                "confidence_score": 0.70,
                "metric_coverage_improvement": 1,
            },
            {
                "metric_key": "kd_nM",
                "suggested_assay": "BLI",
                "expected_readiness_gain": 1,
                "confidence_score": 0.82,
                "metric_coverage_improvement": 1,
            },
            {
                "metric_key": "internalization_score",
                "suggested_assay": "internalization assay",
                "expected_readiness_gain": 0,
                "confidence_score": 0.95,
                "metric_coverage_improvement": 1,
            },
        ]
    )
    assert [r["metric_key"] for r in ranked] == ["kd_nM", "sec_monomer_pct", "internalization_score"]
    assert ranked[0]["effort_estimate"] <= ranked[2]["effort_estimate"]


def test_build_program_trajectory_aggregates_across_molecules() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-progtraj", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m1 = Molecule(program_id=int(p.id), primary_id="M1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p.id), primary_id="M2", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2]); db.commit(); db.refresh(m1); db.refresh(m2)
            for mid, mk in ((int(m1.id), "kd_nM"), (int(m2.id), "sec_monomer_pct")):
                db.add(
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=mid,
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v1",
                        inputs_json="{}",
                        outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"g": {"status": "fail", "missing": [mk], "failed_metrics": []}}, "blockers": []}),
                        evidence_ids_json="[]",
                        is_superseded=0,
                        created_at=now,
                    )
                )
            db.commit()
            out = build_program_trajectory(db, program_id=int(p.id), limit=10)
            assert int(out["program_id"]) == int(p.id)
            assert len(out["experiments"]) >= 2
            assert {int(x["molecule_id"]) for x in out["experiments"]} >= {int(m1.id), int(m2.id)}
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_portfolio_trajectory_collects_global_impact_rows() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p1 = Program(name="PA", created_at=now, updated_at=now)
            p2 = Program(name="PB", created_at=now, updated_at=now)
            db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)
            m1 = Molecule(program_id=int(p1.id), primary_id="A1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p2.id), primary_id="B1", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2]); db.commit(); db.refresh(m1); db.refresh(m2)
            for p, m, mk in ((p1, m1, "kd_nM"), (p2, m2, "sec_monomer_pct")):
                db.add(
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=int(m.id),
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v1",
                        inputs_json="{}",
                        outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"g": {"status": "fail", "missing": [mk], "failed_metrics": []}}, "blockers": []}),
                        evidence_ids_json="[]",
                        is_superseded=0,
                        created_at=now,
                    )
                )
            db.commit()
            out = build_portfolio_trajectory(db, limit=20)
            assert len(out["experiments"]) >= 2
            assert {str(x["program_name"]) for x in out["experiments"]} >= {"PA", "PB"}
        finally:
            db.close()
    finally:
        eng.dispose()


def test_simulate_experiment_set_returns_cumulative_projection() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-set", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-set", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"g": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}}, "blockers": []}),
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            db.commit()
            out = simulate_experiment_set(
                db,
                molecule_id=int(m.id),
                experiments=[
                    {"metric_key": "kd_nM", "simulated_value": 1.2},
                    {"metric_key": "sec_monomer_pct", "simulated_value": 95.0},
                ],
            )
            assert int(out["molecule_id"]) == int(m.id)
            assert int(out["experiment_count"]) == 2
            assert "cumulative_readiness_change" in out
            assert "kd_nM" in out["impacted_metrics"]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_trajectory_tree_has_deterministic_node_ordering() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-tree", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-tree", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"g": {"status": "fail", "missing": ["kd_nM", "sec_monomer_pct"], "failed_metrics": []}}, "blockers": []}),
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            db.commit()
            a = build_trajectory_tree(db, molecule_id=int(m.id), max_depth=2, branch_limit=3)
            b = build_trajectory_tree(db, molecule_id=int(m.id), max_depth=2, branch_limit=3)
            assert a == b
            assert a["nodes"][0]["node_id"] == "root"
            assert all("node_id" in n and "parent_id" in n for n in a["nodes"])
        finally:
            db.close()
    finally:
        eng.dispose()
