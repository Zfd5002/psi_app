from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, Molecule, Program
from psi.services import dev_board
from psi.services import experiment_tasks as task_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_task_ops_do_not_mutate_decision_snapshot_payload() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-boundary", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-BND", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            out_payload = {"decision_state": "ready", "gate_outcomes": {"G1": {"status": "pass"}}, "blockers": []}
            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json=json.dumps(out_payload, sort_keys=True),
                evidence_ids_json="[]",
                is_superseded=0,
                created_at=now,
            )
            db.add(snap)
            db.commit()
            db.refresh(snap)
            before = str(snap.outputs_json)

            t = task_svc.create_experiment_task(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                source_kind="board",
                source_snapshot_id=int(snap.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
            )
            _ = task_svc.assign_task_owner(db, task_id=int(t.id), owner_text="Dr. R")
            _ = task_svc.set_task_due_date(db, task_id=int(t.id), due_date="2026-03-12")
            _ = task_svc.update_task_status(db, task_id=int(t.id), status="in_progress")

            db.refresh(snap)
            after = str(snap.outputs_json)
            assert before == after
        finally:
            db.close()
    finally:
        eng.dispose()


def test_task_linking_uses_existing_data_record_only() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-link-boundary", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-BND2", title="m2", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            rec = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="existing evidence",
                run_date="2026-03-07",
                created_at=now,
                updated_at=now,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            before_n = int(db.query(DataRecord).count())
            t = task_svc.create_experiment_task(db, program_id=int(p.id), molecule_id=int(m.id))
            _ = task_svc.link_task_to_data_record(db, task_id=int(t.id), data_record_id=int(rec.id))
            after_n = int(db.query(DataRecord).count())
            db.refresh(t)
            assert before_n == after_n
            assert int(t.linked_data_record_id) == int(rec.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_board_with_tasks_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-board-det", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-DET", title="d", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
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
            _ = task_svc.create_experiment_task(db, program_id=int(p.id), molecule_id=int(m.id), urgency="high", status="planned", metric_key="a")
            _ = task_svc.create_experiment_task(db, program_id=int(p.id), molecule_id=int(m.id), urgency="critical", status="in_progress", metric_key="b")
            dev_board.invalidate_program_board_cache(program_id=int(p.id))
            a = dev_board.build_development_board(db, program_id=int(p.id), use_cache=False)
            b = dev_board.build_development_board(db, program_id=int(p.id), use_cache=False)
            assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
        finally:
            db.close()
    finally:
        eng.dispose()
