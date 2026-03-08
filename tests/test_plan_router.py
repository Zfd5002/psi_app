from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

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


class _DummyTemplates:
    @staticmethod
    def TemplateResponse(_name: str, ctx: dict):
        return SimpleNamespace(context=ctx)


def test_plan_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in plans_router.router.routes}
    assert ("/plans", ("GET",)) in route_keys
    assert ("/plans/{plan_id}", ("GET",)) in route_keys
    assert ("/plans/{plan_id}/instantiate", ("POST",)) in route_keys
    assert ("/plans/steps/{step_id}/instantiate", ("POST",)) in route_keys


def test_plan_detail_route_context(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    monkeypatch.setattr(plans_router, "get_templates", lambda _request: _DummyTemplates())
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-pr", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-pr", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Readiness plan",
                plan_type="readiness_advancement",
                status="recommended",
            )
            plans_svc.add_plan_step(db, plan_id=int(plan.id), step_kind="experiment", metric_key="kd_nM", suggested_assay="SPR")
            resp = plans_router.plan_detail(plan_id=int(plan.id), request=SimpleNamespace(), db=db)
            assert "plan" in resp.context
            assert int(resp.context["plan"].id) == int(plan.id)
            assert "steps" in resp.context
            assert len(resp.context["steps"]) == 1
            r1 = plans_router.instantiate_plan(plan_id=int(plan.id), request=SimpleNamespace(), redirect_to=f"/plans/{int(plan.id)}", db=db)
            assert int(getattr(r1, "status_code", 0)) == 303
        finally:
            db.close()
    finally:
        eng.dispose()
