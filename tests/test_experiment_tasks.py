from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, Molecule, Program
from psi.services import experiment_tasks as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_create_and_list_tasks_deterministic_ordering() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-svc", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-T1", title="m1", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            t1 = svc.create_experiment_task(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
                status="planned",
                urgency="high",
                due_date="2026-03-10",
            )
            t2 = svc.create_experiment_task(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="tm_c",
                suggested_assay="DSF",
                status="in_progress",
                urgency="normal",
                due_date="2026-03-12",
            )
            t3 = svc.create_experiment_task(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="sec_monomer_pct",
                suggested_assay="SEC_HPLC",
                status="blocked",
                urgency="critical",
                due_date="2026-03-08",
            )
            svc.update_task_status(db, task_id=int(t3.id), status="in_progress")
            svc.update_task_status(db, task_id=int(t3.id), status="done")

            rows = svc.list_tasks_for_program(db, program_id=int(p.id), include_done=True)
            assert [int(x.id) for x in rows] == [int(t2.id), int(t1.id), int(t3.id)]
            open_rows = svc.list_tasks_for_program(db, program_id=int(p.id), include_done=False)
            assert [int(x.id) for x in open_rows] == [int(t1.id), int(t2.id)]
            top = svc.top_open_task_for_molecule(db, molecule_id=int(m.id))
            assert top is not None
            assert int(top.id) == int(t1.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_lifecycle_owner_due_date_and_linking_rules() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-link", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-T2", title="m2", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            rec = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                domain="BIO",
                data_type="Binding",
                method="SPR",
                title="record",
                run_date="2026-03-07",
                created_at=now,
                updated_at=now,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)

            t = svc.create_experiment_task(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                status="planned",
                urgency="unknown",
            )
            assert str(t.urgency) == "normal"
            t = svc.assign_task_owner(db, task_id=int(t.id), owner_text="Dr. K")
            t = svc.set_task_due_date(db, task_id=int(t.id), due_date="2026-03-09")
            assert str(t.owner_text or "") == "Dr. K"
            assert str(t.due_date or "") == "2026-03-09"

            t = svc.update_task_status(db, task_id=int(t.id), status="in_progress")
            assert str(t.status) == "in_progress"
            t = svc.update_task_status(db, task_id=int(t.id), status="done")
            assert str(t.status) == "done"

            try:
                svc.update_task_status(db, task_id=int(t.id), status="in_progress")
                assert False, "expected terminal done behavior"
            except ValueError as e:
                assert str(e) == "done_task_is_terminal"

            t2 = svc.create_experiment_task(db, program_id=int(p.id), molecule_id=int(m.id))
            t2 = svc.link_task_to_data_record(db, task_id=int(t2.id), data_record_id=int(rec.id))
            assert int(t2.linked_data_record_id) == int(rec.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_transition_graph_enforced() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-transition", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-T3", title="m3", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            planned = svc.create_experiment_task(db, program_id=int(p.id), molecule_id=int(m.id), status="planned")
            try:
                svc.update_task_status(db, task_id=int(planned.id), status="done")
                assert False, "expected invalid planned->done transition"
            except ValueError as e:
                assert str(e) == "invalid_task_transition"

            blocked = svc.update_task_status(db, task_id=int(planned.id), status="blocked")
            assert str(blocked.status) == "blocked"
            resumed = svc.update_task_status(db, task_id=int(planned.id), status="in_progress")
            assert str(resumed.status) == "in_progress"
            done = svc.update_task_status(db, task_id=int(planned.id), status="done")
            assert str(done.status) == "done"
        finally:
            db.close()
    finally:
        eng.dispose()
