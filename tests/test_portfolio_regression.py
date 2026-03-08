from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services.dev_board import build_development_board
from psi.services.portfolio import (
    build_evidence_gap_report,
    build_molecule_leaderboard,
    build_portfolio_export_rows,
    build_portfolio_program_summaries,
    build_portfolio_summary,
    build_portfolio_timeline,
)
from psi.web.routers import data_records as data_records_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_portfolio_summary_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-det", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-det", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}),
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            db.add(ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="in_progress", created_at=now, updated_at=now))
            db.commit()

            a = build_portfolio_summary(db)
            b = build_portfolio_summary(db)
            assert a == b
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_read_model_does_not_mutate_decision_snapshots() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-di", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-di", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"G": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}}, "blockers": []}),
                evidence_ids_json="[]",
                is_superseded=0,
                created_at=now,
            )
            db.add(snap)
            db.commit()
            db.refresh(snap)
            before_outputs = str(snap.outputs_json)

            _ = build_portfolio_summary(db)
            _ = build_portfolio_program_summaries(db)
            _ = build_molecule_leaderboard(db, limit=10)
            _ = build_evidence_gap_report(db, limit=10)
            _ = build_portfolio_timeline(db, weeks=4)
            _ = build_portfolio_export_rows(db)

            db.refresh(snap)
            assert str(snap.outputs_json) == before_outputs
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_queries_do_not_change_board_grouping() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-board", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-board", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}),
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            db.commit()

            board_before = build_development_board(db, program_id=int(p.id), use_cache=False)
            _ = build_portfolio_summary(db)
            _ = build_portfolio_program_summaries(db)
            _ = build_evidence_gap_report(db)
            board_after = build_development_board(db, program_id=int(p.id), use_cache=False)
            assert board_before == board_after
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_layer_does_not_break_task_datarecord_linking() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-link", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-link", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-link", title="", created_at=now, updated_at=now)
            db.add(b); db.commit(); db.refresh(b)
            t = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now, updated_at=now)
            db.add(t); db.commit(); db.refresh(t)

            _ = build_portfolio_summary(db)
            resp = data_records_router.create_data(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="link regression",
                task_id=int(t.id),
                notes="",
                run_date="2026-03-07",
                params_json="{}",
                results_json='{"kd_nM": 1.2}',
                files=[],
                db=db,
                storage=None,
            )
            assert int(resp.status_code) == 303
            rec = db.query(DataRecord).order_by(DataRecord.id.desc()).first()
            assert rec is not None
            db.refresh(t)
            assert int(t.linked_data_record_id) == int(rec.id)
            assert str(t.status) == "done"
        finally:
            db.close()
    finally:
        eng.dispose()
