from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import (
    Base,
    Molecule,
    Program,
    ScientificClaim,
    ScientificPlan,
    ScientificPlanStep,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_scientific_plan_tables_and_columns_exist() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            tables = {r[0] for r in db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
            assert "scientific_plans" in tables
            assert "scientific_plan_steps" in tables
            cols = {r[1] for r in db.execute(text("PRAGMA table_info(scientific_plans)"))}
            assert {"scope_type", "plan_type", "status", "expected_readiness_gain"} <= cols
            step_cols = {r[1] for r in db.execute(text("PRAGMA table_info(scientific_plan_steps)"))}
            assert {"plan_id", "step_order", "step_kind", "status"} <= step_cols
        finally:
            db.close()
    finally:
        eng.dispose()


def test_scientific_plan_lifecycle_and_steps_are_additive() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-model", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-model", title="", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            c = ScientificClaim(
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Claim",
                claim_type="mechanism",
                statement="Mechanism claim",
                status="hypothesis",
                confidence_level="low",
                created_at=now,
                updated_at=now,
            )
            db.add(c)
            db.commit()
            db.refresh(c)

            plan = ScientificPlan(
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=int(c.id),
                title="Readiness bundle",
                plan_type="readiness_advancement",
                status="draft",
                rationale="fill missing metrics first",
                expected_readiness_gain=1.0,
                expected_claim_support_gain=0.3,
                expected_evidence_coverage_gain=0.5,
                created_at=now,
                updated_at=now,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)

            step = ScientificPlanStep(
                plan_id=int(plan.id),
                step_order=1,
                metric_key="kd_nM",
                suggested_assay="SPR",
                step_kind="experiment",
                rationale="affinity gap",
                expected_effect_summary="reduces readiness blocker",
                status="proposed",
                created_at=now,
                updated_at=now,
            )
            db.add(step)
            db.commit()

            assert int(db.query(ScientificPlan).count()) == 1
            assert int(db.query(ScientificPlanStep).count()) == 1
        finally:
            db.close()
    finally:
        eng.dispose()
