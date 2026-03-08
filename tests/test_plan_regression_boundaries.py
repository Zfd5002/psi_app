from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services import claims as claims_svc
from psi.services import plans as plans_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _seed_state(db):
    now = datetime(2026, 3, 7)
    p = Program(name="P-plan-reg", created_at=now, updated_at=now)
    db.add(p); db.commit(); db.refresh(p)
    m = Molecule(program_id=int(p.id), primary_id="M-plan-reg", title="", created_at=now, updated_at=now)
    db.add(m); db.commit(); db.refresh(m)
    output = {
        "decision_state": "not_ready",
        "gate_outcomes": {"g": {"status": "hold", "missing": ["kd_nM"], "failed_metrics": []}},
        "recommended_experiments": [{"priority": 1, "metric_key": "kd_nM", "suggested_assay": "SPR", "reason": "fill gap"}],
        "blockers": [],
    }
    snap = DecisionSnapshot(
        program_id=int(p.id), molecule_id=int(m.id), batch_id=None,
        decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}",
        outputs_json=json.dumps(output), evidence_ids_json="[]", is_superseded=0, created_at=now,
    )
    task = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", metric_key="tm_c", created_at=now, updated_at=now)
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
        confidence_level="medium",
    )
    return p, m, snap, task, claim


def test_plan_generation_does_not_mutate_di_claim_or_task_truth() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m, snap, task, claim = _seed_state(db)
            before_output = str(snap.outputs_json or "")
            before_task_status = str(task.status or "")
            before_claim_status = str(claim.status or "")
            before_claim_conf = str(claim.confidence_level or "")
            before_records = int(db.query(DataRecord).count())

            plans_svc.generate_plan_for_molecule(db, molecule_id=int(m.id))
            plans_svc.generate_plan_for_claim(db, claim_id=int(claim.id))

            snap2 = db.get(DecisionSnapshot, int(snap.id))
            task2 = db.get(ExperimentTask, int(task.id))
            claim2 = db.get(type(claim), int(claim.id))
            assert str(snap2.outputs_json or "") == before_output
            assert str(task2.status or "") == before_task_status
            assert str(claim2.status or "") == before_claim_status
            assert str(claim2.confidence_level or "") == before_claim_conf
            assert int(db.query(DataRecord).count()) == before_records
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_ordering_and_summary_are_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            _p, m, _snap, _task, claim = _seed_state(db)
            p1 = plans_svc.generate_plan_for_molecule(db, molecule_id=int(m.id))["plan"]
            p2 = plans_svc.generate_plan_for_claim(db, claim_id=int(claim.id))["plan"]
            rows1 = plans_svc.top_plans_for_molecule(db, molecule_id=int(m.id), limit=10)
            rows2 = plans_svc.top_plans_for_molecule(db, molecule_id=int(m.id), limit=10)
            assert [int(x.id) for x in rows1] == [int(x.id) for x in rows2]
            d1 = plans_svc.build_plan_detail(db, plan_id=int(p1.id))
            d2 = plans_svc.build_plan_detail(db, plan_id=int(p1.id))
            assert float(d1["plan_score"]) == float(d2["plan_score"])
            assert int(d1["effort_estimate"]) == int(d2["effort_estimate"])
            assert int(p2.id) in {int(x.id) for x in plans_svc.top_plans_for_claim(db, claim_id=int(claim.id), limit=10)}
        finally:
            db.close()
    finally:
        eng.dispose()
