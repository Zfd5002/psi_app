from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import plans as plans_svc
from psi.web.routers import programs as programs_router


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


def test_program_narrative_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in programs_router.router.routes}
    assert ("/programs/{program_id}/narrative", ("GET",)) in route_keys
    assert ("/programs/{program_id}/narrative/export", ("GET",)) in route_keys


def test_program_narrative_route_context(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    monkeypatch.setattr(programs_router, "get_templates", lambda _request: _DummyTemplates())
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-pnr", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-pnr", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="Plan", plan_type="readiness_advancement", status="recommended")
            plans_svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment")
            resp = programs_router.program_narrative_detail(program_id=int(p.id), request=SimpleNamespace(), db=db)
            assert "program" in resp.context
            assert "narrative" in resp.context
            assert int(resp.context["program"].id) == int(p.id)
            bref = programs_router.program_narrative_detail(program_id=int(p.id), request=SimpleNamespace(query_params={"view": "brief"}), db=db)
            assert bool(bref.context.get("narrative_brief")) is True
            ex = programs_router.program_narrative_export(program_id=int(p.id), db=db)
            txt = str(ex.body.decode("utf-8"))
            assert "Program Narrative Export" in txt
            assert "Scientific thesis:" in txt
        finally:
            db.close()
    finally:
        eng.dispose()
