from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services import claims as claims_svc
from psi.web.routers import claims as claims_router


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


def test_claim_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in claims_router.router.routes}
    assert ("/claims", ("GET",)) in route_keys
    assert ("/claims/{claim_id}", ("GET",)) in route_keys


def test_claim_detail_route_context(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    monkeypatch.setattr(claims_router, "get_templates", lambda _request: _DummyTemplates())
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-cr", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-cr", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = claims_svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Claim", claim_type="affinity", statement="x")
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json='{"decision_state":"not_ready","gate_outcomes":{"g":{"status":"fail","missing":["kd_nM"],"failed_metrics":[]}},"blockers":[]}',
                    evidence_ids_json="[]",
                    is_superseded=0,
                    created_at=now,
                )
            )
            t = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", suggested_assay="BLI", metric_key="kd_nM", created_at=now, updated_at=now)
            db.add(t); db.commit(); db.refresh(t)
            claims_svc.link_claim_to_task(db, claim_id=int(c.id), experiment_task_id=int(t.id), relationship_type="tests")
            resp = claims_router.claim_detail(claim_id=int(c.id), request=SimpleNamespace(), db=db)
            assert "claim" in resp.context
            assert int(resp.context["claim"].id) == int(c.id)
            assert "maturity" in resp.context
            assert "open_linked_tasks" in resp.context
            assert "trajectory_candidates" in resp.context
            assert "claim_plans" in resp.context
        finally:
            db.close()
    finally:
        eng.dispose()
