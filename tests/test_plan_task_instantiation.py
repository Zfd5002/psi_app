from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, ExperimentTask, Molecule, Program
from psi.services import plans as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_create_task_from_plan_step_links_and_sets_status() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-task", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-task", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="Plan", plan_type="readiness_advancement", status="recommended")
            step = svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment", status="proposed")
            task = svc.create_task_from_plan_step(db, step_id=int(step.id))
            assert int(task.id) > 0
            step2 = db.get(type(step), int(step.id))
            assert int(step2.linked_experiment_task_id) == int(task.id)
            assert str(step2.status) == "task_created"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_create_tasks_from_plan_instantiates_proposed_steps_only() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-task-all", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-task-all", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="Plan", plan_type="readiness_advancement", status="recommended")
            s1 = svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment", status="proposed")
            s2 = svc.add_plan_step(db, plan_id=int(plan.id), metric_key="sec_monomer_pct", suggested_assay="SEC", step_kind="experiment", status="proposed")
            created = svc.create_tasks_from_plan(db, plan_id=int(plan.id))
            assert len(created) == 2
            assert int(db.query(ExperimentTask).count()) == 2
            rows = svc.list_plan_steps(db, plan_id=int(plan.id))
            assert all(str(x.status) == "task_created" for x in rows if int(x.id) in {int(s1.id), int(s2.id)})
        finally:
            db.close()
    finally:
        eng.dispose()
