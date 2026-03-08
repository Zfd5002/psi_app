from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.services import claims as claims_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_detail_includes_recommended_plans_context() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-cp", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-cp", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id), molecule_id=int(m.id), batch_id=None,
                    decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}",
                    outputs_json='{"decision_state":"not_ready","gate_outcomes":{"g":{"status":"hold","missing":["kd_nM"],"failed_metrics":[]}},"recommended_experiments":[{"priority":1,"metric_key":"kd_nM","suggested_assay":"SPR","reason":"fill gap"}],"blockers":[]}',
                    evidence_ids_json="[]", is_superseded=0, created_at=now,
                )
            )
            db.commit()
            c = claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Affinity claim",
                claim_type="affinity",
                statement="x",
                status="emerging",
            )
            detail = claims_svc.get_claim_detail(db, claim_id=int(c.id))
            assert "claim_plans" in detail
            assert len(detail["claim_plans"]) >= 1
        finally:
            db.close()
    finally:
        eng.dispose()
