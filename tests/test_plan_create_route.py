from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program, ScientificClaim, ScientificPlan
from psi.services import claims as claims_svc
from psi.web.routers import plans as plans_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_plan_create_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in plans_router.router.routes}
    assert ("/plans/new", ("GET",)) in route_keys
    assert ("/plans/new", ("POST",)) in route_keys


def test_plan_create_route_creates_molecule_scope_plan() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-plan-new", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-new", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            resp = plans_router.plan_create(
                request=None,
                scope_type="molecule",
                molecule_id=int(m.id),
                claim_id=None,
                title="Readiness bundle",
                plan_type="readiness_advancement",
                rationale="Fill gating evidence first",
                db=db,
            )
            assert int(getattr(resp, "status_code", 0)) == 303
            rows = db.query(ScientificPlan).order_by(ScientificPlan.id.asc()).all()
            assert len(rows) == 1
            row = rows[0]
            assert str(row.scope_type) == "molecule"
            assert int(row.molecule_id) == int(m.id)
            assert int(row.program_id) == int(p.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_create_route_creates_claim_scope_plan() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-plan-claim", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-claim", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Claim",
                claim_type="affinity",
                statement="test",
            )
            _ = plans_router.plan_create(
                request=None,
                scope_type="claim",
                molecule_id=None,
                claim_id=int(c.id),
                title="Claim de-risking bundle",
                plan_type="claim_de_risking",
                rationale="Resolve support gaps",
                db=db,
            )
            row = db.query(ScientificPlan).order_by(ScientificPlan.id.desc()).first()
            assert row is not None
            assert str(row.scope_type) == "claim"
            assert int(row.claim_id) == int(c.id)
            assert int(row.molecule_id) == int(m.id)
        finally:
            db.close()
    finally:
        eng.dispose()
