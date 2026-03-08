from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import claims as claims_svc
from psi.services import experiment_tasks as task_svc
from psi.services import plans as plans_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_board_cache_invalidation_runs_on_task_claim_and_plan_writes(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    calls: list[int] = []

    def _spy(*, program_id: int | None = None):
        if program_id is not None:
            calls.append(int(program_id))

    monkeypatch.setattr(task_svc, "invalidate_program_board_cache", _spy)
    monkeypatch.setattr(claims_svc, "invalidate_program_board_cache", _spy)
    monkeypatch.setattr(plans_svc, "invalidate_program_board_cache", _spy)

    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-inv", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-inv", title="", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            t = task_svc.create_experiment_task(db, program_id=int(p.id), molecule_id=int(m.id), metric_key="kd_nM")
            task_svc.update_task_status(db, task_id=int(t.id), status="in_progress")
            task_svc.update_task_status(db, task_id=int(t.id), status="done")

            c = claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Affinity claim",
                claim_type="affinity",
                statement="Molecule has sufficient affinity",
            )
            claims_svc.update_claim_status(db, claim_id=int(c.id), status="emerging")

            plan = plans_svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Readiness plan",
                plan_type="readiness_advancement",
                status="draft",
            )
            step = plans_svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="BLI")
            plans_svc.update_plan_step_status(db, step_id=int(step.id), status="task_created")
            plans_svc.update_plan_status(db, plan_id=int(plan.id), status="recommended")
        finally:
            db.close()
    finally:
        eng.dispose()

    assert len(calls) >= 7
    assert all(int(x) == int(calls[0]) for x in calls)
