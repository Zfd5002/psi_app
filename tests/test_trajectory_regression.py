from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services.dev_board import build_development_board
from psi.services.trajectory import (
    build_portfolio_trajectory,
    build_program_trajectory,
    build_trajectory_tree,
    generate_trajectory_candidates,
    rank_trajectory_candidates,
    simulate_experiment_outcome,
    simulate_experiment_set,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_trajectory_simulation_does_not_mutate_snapshot_or_task_state() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-reg", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-reg", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            snap = DecisionSnapshot(
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
            task = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="BLI",
                status="planned",
                created_at=now,
                updated_at=now,
            )
            db.add_all([snap, task]); db.commit(); db.refresh(snap); db.refresh(task)
            outputs_before = str(snap.outputs_json)
            status_before = str(task.status)
            linked_before = task.linked_data_record_id

            _ = simulate_experiment_outcome(db, molecule_id=int(m.id), metric_key="kd_nM", simulated_value=1.0)
            _ = simulate_experiment_set(db, molecule_id=int(m.id), experiments=[{"metric_key": "kd_nM", "simulated_value": 1.0}])
            _ = rank_trajectory_candidates(generate_trajectory_candidates(db, molecule_id=int(m.id)))
            _ = build_trajectory_tree(db, molecule_id=int(m.id), max_depth=2, branch_limit=3)
            _ = build_program_trajectory(db, program_id=int(p.id))
            _ = build_portfolio_trajectory(db)

            db.refresh(snap); db.refresh(task)
            assert str(snap.outputs_json) == outputs_before
            assert str(task.status) == status_before
            assert task.linked_data_record_id == linked_before
        finally:
            db.close()
    finally:
        eng.dispose()


def test_trajectory_reads_do_not_change_board_output() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-board-reg", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-board-reg", title="", created_at=now, updated_at=now)
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
            before = build_development_board(db, program_id=int(p.id), use_cache=False)
            _ = build_trajectory_tree(db, molecule_id=int(m.id), max_depth=2, branch_limit=3)
            _ = build_program_trajectory(db, program_id=int(p.id))
            after = build_development_board(db, program_id=int(p.id), use_cache=False)
            assert before == after
        finally:
            db.close()
    finally:
        eng.dispose()
