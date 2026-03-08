from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import plans as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_plan_scoring_and_ranking_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-rank", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-rank", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)

            a = svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="A", plan_type="readiness_advancement", status="recommended", expected_readiness_gain=1.0, expected_claim_support_gain=0.1, expected_evidence_coverage_gain=0.1)
            b = svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="B", plan_type="evidence_completion", status="recommended", expected_readiness_gain=0.3, expected_claim_support_gain=0.2, expected_evidence_coverage_gain=0.9)
            svc.add_plan_step(db, plan_id=int(a.id), step_kind="experiment")
            svc.add_plan_step(db, plan_id=int(a.id), step_kind="confirmatory")
            svc.add_plan_step(db, plan_id=int(b.id), step_kind="experiment")

            ra = svc.score_plan(db, a)
            rb = svc.score_plan(db, b)
            ranked = svc.rank_plans(db, [a, b])
            assert isinstance(ra, float)
            assert isinstance(rb, float)
            assert len(ranked) == 2
            assert sorted([int(x.id) for x in ranked]) == [int(a.id), int(b.id)]

            top = svc.top_plans_for_molecule(db, molecule_id=int(m.id), limit=2)
            assert [int(x.id) for x in top] == [int(x.id) for x in ranked]
        finally:
            db.close()
    finally:
        eng.dispose()
