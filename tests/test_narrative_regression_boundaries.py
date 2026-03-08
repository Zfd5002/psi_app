from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services import claims as claims_svc
from psi.services import narratives as narrative_svc
from psi.services import plans as plans_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _seed(db):
    now = datetime(2026, 3, 7)
    p = Program(name="P-nreg", created_at=now, updated_at=now)
    db.add(p); db.commit(); db.refresh(p)
    m = Molecule(program_id=int(p.id), primary_id="M-nreg", title="", created_at=now, updated_at=now)
    db.add(m); db.commit(); db.refresh(m)
    out = {
        "decision_state": "not_ready",
        "gate_outcomes": {"g": {"status": "hold", "missing": ["kd_nM"], "failed_metrics": []}},
        "recommended_experiments": [{"priority": 1, "metric_key": "kd_nM", "suggested_assay": "SPR", "reason": "fill gap"}],
        "blockers": [],
    }
    snap = DecisionSnapshot(
        program_id=int(p.id), molecule_id=int(m.id), batch_id=None,
        decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}",
        outputs_json=json.dumps(out), evidence_ids_json="[]", is_superseded=0, created_at=now,
    )
    task = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now, updated_at=now)
    db.add_all([snap, task]); db.commit(); db.refresh(snap); db.refresh(task)
    claim = claims_svc.create_claim(
        db,
        scope_type="molecule",
        molecule_id=int(m.id),
        program_id=int(p.id),
        title="Affinity claim",
        claim_type="affinity",
        statement="x",
        status="emerging",
    )
    plan = plans_svc.create_plan(
        db,
        scope_type="molecule",
        molecule_id=int(m.id),
        program_id=int(p.id),
        claim_id=None,
        title="Readiness plan",
        plan_type="readiness_advancement",
        status="recommended",
        expected_readiness_gain=1.0,
    )
    plans_svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment")
    return p, snap, task, claim, plan


def test_narrative_builders_do_not_mutate_scientific_or_operational_truth() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p, snap, task, claim, plan = _seed(db)
            before_snap = str(snap.outputs_json or "")
            before_task = str(task.status or "")
            before_claim = str(claim.status or "")
            before_plan = str(plan.status or "")

            _pn = narrative_svc.build_program_narrative(db, program_id=int(p.id))
            _pt = narrative_svc.build_portfolio_narrative(db)

            snap2 = db.get(DecisionSnapshot, int(snap.id))
            task2 = db.get(ExperimentTask, int(task.id))
            claim2 = claims_svc.get_claim(db, claim_id=int(claim.id))
            plan2 = plans_svc.get_plan(db, plan_id=int(plan.id))
            assert str(snap2.outputs_json or "") == before_snap
            assert str(task2.status or "") == before_task
            assert str(claim2.status or "") == before_claim
            assert str(plan2.status or "") == before_plan
        finally:
            db.close()
    finally:
        eng.dispose()


def test_narrative_outputs_are_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p, _snap, _task, _claim, _plan = _seed(db)
            n1 = narrative_svc.build_program_narrative(db, program_id=int(p.id))
            n2 = narrative_svc.build_program_narrative(db, program_id=int(p.id))
            assert n1 == n2
            pf1 = narrative_svc.build_portfolio_narrative(db)
            pf2 = narrative_svc.build_portfolio_narrative(db)
            assert pf1 == pf2
        finally:
            db.close()
    finally:
        eng.dispose()
