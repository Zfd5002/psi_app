from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from psi.core.models import Molecule, Program
from psi.web.routers import portfolio as portfolio_router


def test_portfolio_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in portfolio_router.router.routes}
    assert ("/portfolio", ("GET",)) in route_keys
    assert ("/portfolio/export", ("GET",)) in route_keys
    assert ("/portfolio/narrative/export", ("GET",)) in route_keys


def test_portfolio_route_context(monkeypatch, mkdb, dummy_templates) -> None:
    eng, SessionTmp = mkdb()
    monkeypatch.setattr(portfolio_router, "get_templates", lambda _request: dummy_templates)
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-rt", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-rt", title="", created_at=now, updated_at=now)
            db.add(m); db.commit()
            req = SimpleNamespace()
            resp = portfolio_router.portfolio_overview(request=req, db=db)
            assert "portfolio_summary" in resp.context
            assert "program_summaries" in resp.context
            assert "portfolio_timeline" in resp.context
            assert "portfolio_trajectory" in resp.context
            assert "portfolio_claim_summary" in resp.context
            assert "portfolio_plan_summary" in resp.context
            assert "portfolio_narrative" in resp.context
            assert isinstance(resp.context["program_summaries"], list)
            bresp = portfolio_router.portfolio_overview(request=SimpleNamespace(query_params={"view": "brief"}), db=db)
            assert bool(bresp.context.get("narrative_brief")) is True
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_export_csv_contains_program_rollup(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-csv", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-csv", title="", created_at=now, updated_at=now)
            db.add(m); db.commit()
            resp = portfolio_router.portfolio_export(db=db)
            text = str(resp.body.decode("utf-8"))
            assert "program_id,program_name,program_status,readiness_score" in text
            assert "P-csv" in text
            assert "text/csv" in str(resp.media_type)
            assert "portfolio_summary.csv" in str(resp.headers.get("Content-Disposition", ""))
            nresp = portfolio_router.portfolio_narrative_export(db=db)
            ntxt = str(nresp.body.decode("utf-8"))
            assert "Portfolio Narrative Export" in ntxt
            assert "Key bottlenecks:" in ntxt
            assert "portfolio_narrative.txt" in str(nresp.headers.get("Content-Disposition", ""))
        finally:
            db.close()
    finally:
        eng.dispose()
