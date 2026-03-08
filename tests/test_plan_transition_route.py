from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import plans as plans_svc
from psi.web.routers import plans as plans_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_plan_transition_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in plans_router.router.routes}
    assert ("/plans/{plan_id}/transition", ("POST",)) in route_keys


def test_plan_transition_route_applies_allowed_transitions() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-plan-tr", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-tr", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan",
                plan_type="readiness_advancement",
                status="draft",
            )
            r1 = plans_router.transition_plan(plan_id=int(plan.id), request=None, status="recommended", redirect_to="", db=db)
            assert int(getattr(r1, "status_code", 0)) == 303
            r2 = plans_router.transition_plan(plan_id=int(plan.id), request=None, status="accepted", redirect_to="", db=db)
            assert int(getattr(r2, "status_code", 0)) == 303
            r3 = plans_router.transition_plan(plan_id=int(plan.id), request=None, status="archived", redirect_to="", db=db)
            assert int(getattr(r3, "status_code", 0)) == 303
            row = plans_svc.get_plan(db, plan_id=int(plan.id))
            assert row is not None
            assert str(row.status) == "archived"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_transition_route_rejects_invalid_transition() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-plan-tr-bad", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-tr-bad", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan",
                plan_type="readiness_advancement",
                status="draft",
            )
            with pytest.raises(HTTPException) as exc:
                plans_router.transition_plan(plan_id=int(plan.id), request=None, status="accepted", redirect_to="", db=db)
            assert int(exc.value.status_code) == 400
            row = plans_svc.get_plan(db, plan_id=int(plan.id))
            assert row is not None
            assert str(row.status) == "draft"
        finally:
            db.close()
    finally:
        eng.dispose()
