from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, Molecule, Program
from psi.services import claims as claims_svc
from psi.services import plans as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _seed_snapshot(db, *, program_id: int, molecule_id: int, now: datetime) -> None:
    output = {
        "decision_state": "not_ready",
        "gate_outcomes": {
            "binding": {"status": "hold", "missing": ["kd_nM"], "failed_metrics": []},
            "developability": {"status": "fail", "missing": ["sec_monomer_pct"], "failed_metrics": ["hwm_pct"]},
        },
        "recommended_experiments": [
            {"priority": 1, "metric_key": "kd_nM", "suggested_assay": "SPR", "reason": "fill missing KD"},
            {"priority": 2, "metric_key": "sec_monomer_pct", "suggested_assay": "SEC", "reason": "close purity gap"},
            {"priority": 3, "metric_key": "hwm_pct", "suggested_assay": "SEC", "reason": "resolve aggregate signal"},
        ],
    }
    snap = DecisionSnapshot(
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        batch_id=None,
        decision_key="advance_to_in_vivo",
        rules_version="v1",
        inputs_json="{}",
        outputs_json=json.dumps(output),
        evidence_ids_json="[]",
        is_superseded=0,
        created_at=now,
    )
    db.add(snap)
    db.commit()


def test_generate_plan_for_molecule_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-gen", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-gen", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            _seed_snapshot(db, program_id=int(p.id), molecule_id=int(m.id), now=now)

            out1 = svc.generate_plan_for_molecule(db, molecule_id=int(m.id))
            out2 = svc.generate_plan_for_molecule(db, molecule_id=int(m.id))
            p1 = out1["plan"]
            p2 = out2["plan"]
            assert int(p1.id) == int(p2.id)
            assert str(p1.status) == "recommended"
            steps = svc.list_plan_steps(db, plan_id=int(p1.id))
            assert len(steps) >= 2
            assert [int(s.step_order) for s in steps] == sorted(int(s.step_order) for s in steps)
            metric_order = [str(s.metric_key or "") for s in steps]
            assert "kd_nM" in metric_order[:2]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_generate_plan_for_claim_builds_claim_de_risking_plan() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-claim-plan-gen", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claim-plan-gen", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            _seed_snapshot(db, program_id=int(p.id), molecule_id=int(m.id), now=now)
            claim = claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Affinity claim",
                claim_type="affinity",
                statement="Molecule has strong affinity",
                status="emerging",
                confidence_level="low",
            )
            rec = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="Biological", data_type="Binding", method="SPR", title="r1", created_at=now, updated_at=now)
            db.add(rec); db.commit(); db.refresh(rec)
            claims_svc.link_claim_to_data_record(db, claim_id=int(claim.id), data_record_id=int(rec.id), direction="contradicting")
            out = svc.generate_plan_for_claim(db, claim_id=int(claim.id))
            plan = out["plan"]
            assert str(plan.plan_type) == "claim_de_risking"
            assert int(plan.claim_id) == int(claim.id)
            assert float(plan.expected_claim_support_gain) >= 0.5
            steps = svc.list_plan_steps(db, plan_id=int(plan.id))
            assert steps
            assert any(str(s.step_kind) == "claim_test" for s in steps)
            assert any(str(s.step_kind) == "confirmatory" for s in steps)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_generate_readiness_plan_adds_confirmatory_followup() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-readiness-confirm", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-readiness-confirm", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            _seed_snapshot(db, program_id=int(p.id), molecule_id=int(m.id), now=now)
            out = svc.generate_readiness_plan_for_molecule(db, molecule_id=int(m.id))
            steps = out["steps"]
            assert any(str(s.step_kind) == "confirmatory" for s in steps)
        finally:
            db.close()
    finally:
        eng.dispose()
