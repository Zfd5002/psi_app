from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Evidence, EvidenceCitation, ExperimentTask, Molecule, Program, ScientificClaim, ScientificPlan, ScientificPlanStep
from psi.services import claims as claims_svc
from psi.services import plans as plans_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_detail_includes_header_impact_keys() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-chi", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-CHI", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            c = ScientificClaim(
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="C",
                claim_type="affinity",
                statement="S",
                status="emerging",
                confidence_level="low",
                created_at=now,
                updated_at=now,
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            out = claims_svc.get_claim_detail(db, claim_id=int(c.id))
            hi = out.get("header_impact") or {}
            assert set(hi.keys()) == {"recent_evidence_links", "recent_completed_work", "interpretation_pending"}
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_detail_header_impact_tracks_pending_links() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-phi", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-PHI", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            plan = ScientificPlan(
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Plan",
                plan_type="readiness_advancement",
                status="recommended",
                created_at=now,
                updated_at=now,
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            task = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                status="done",
                linked_data_record_id=123,
                metric_key="kd_nM",
                created_at=now,
                updated_at=now,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            step = ScientificPlanStep(
                plan_id=int(plan.id),
                step_order=1,
                step_kind="experiment",
                status="done",
                linked_experiment_task_id=int(task.id),
                created_at=now,
                updated_at=now,
            )
            db.add(step)
            db.commit()

            ev = Evidence(
                program_id=int(p.id),
                molecule_id=int(m.id),
                domain="Biological",
                evidence_type="binding_support",
                strength=3,
                summary="E",
                created_at=now,
                updated_at=now,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            db.add(EvidenceCitation(evidence_id=int(ev.id), data_record_id=999))
            db.commit()

            out = plans_svc.build_plan_detail(db, plan_id=int(plan.id))
            hi = out.get("header_impact") or {}
            assert set(hi.keys()) == {"new_results_affecting_plan", "evidence_updates", "recent_execution_activity"}
            assert int(hi.get("recent_execution_activity") or 0) >= 1
        finally:
            db.close()
    finally:
        eng.dispose()

