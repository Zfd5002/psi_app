from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import plans as plans_svc
from psi.services import programs as program_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_program_detail_includes_plan_summary_and_preview() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-pps", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-pps", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="Plan", plan_type="readiness_advancement", status="recommended")
            plans_svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment", status="proposed")
            old_sql = program_svc.PROGRAM_EVIDENCE_ROWS_SQL
            program_svc.PROGRAM_EVIDENCE_ROWS_SQL = """
            SELECT dr.molecule_id AS molecule_id, dm.name AS metric_key
            FROM data_records dr
            JOIN data_measurements dm ON dm.data_record_id = dr.id
            WHERE dr.program_id = :pid AND dr.molecule_id IS NOT NULL
            ORDER BY dr.molecule_id ASC, dm.name ASC, dm.id ASC
            """
            ctx = program_svc.get_program_detail(db, int(p.id))
            program_svc.PROGRAM_EVIDENCE_ROWS_SQL = old_sql
            assert "program_plan_summary" in ctx
            assert "program_plans_preview" in ctx
            assert int(ctx["program_plan_summary"]["recommended"]) >= 1
            assert len(ctx["program_plans_preview"]) >= 1
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claim_plan_context_uses_batched_plan_step_lookup() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-pps-batch", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-pps-batch", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan",
                plan_type="readiness_advancement",
                status="recommended",
            )
            plans_svc.add_plan_step(
                db,
                plan_id=int(plan.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
                step_kind="experiment",
                status="proposed",
            )
            calls: list[list[int]] = []
            original_batch = program_svc.plans_svc.list_plan_steps_for_plan_ids

            def _wrapped_batch(db_sess, *, plan_ids):
                calls.append(sorted(int(x) for x in plan_ids))
                return original_batch(db_sess, plan_ids=plan_ids)

            program_svc.plans_svc.list_plan_steps_for_plan_ids = _wrapped_batch
            try:
                ctx = program_svc._build_program_claim_plan_context(db, program_id=int(p.id))
            finally:
                program_svc.plans_svc.list_plan_steps_for_plan_ids = original_batch

            assert calls, "expected batched plan-step lookup"
            assert any(int(plan.id) in call_ids for call_ids in calls)
            assert int(ctx["program_plan_summary"]["recommended"]) >= 1
            assert len(ctx["program_plans_preview"]) >= 1
        finally:
            db.close()
    finally:
        eng.dispose()
