from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.services import claims as claims_svc
from psi.services import narratives as svc
from psi.services import plans as plans_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _seed_program(db, name: str, pid: str):
    now = datetime(2026, 3, 7)
    p = Program(name=name, created_at=now, updated_at=now)
    db.add(p); db.commit(); db.refresh(p)
    m = Molecule(program_id=int(p.id), primary_id=f"M-{pid}", title="", created_at=now, updated_at=now)
    db.add(m); db.commit(); db.refresh(m)
    db.add(
        DecisionSnapshot(
            program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
            inputs_json="{}",
            outputs_json=json.dumps({
                "decision_state": "not_ready",
                "gate_outcomes": {"g": {"status": "hold", "missing": ["kd_nM"], "failed_metrics": []}},
                "recommended_experiments": [{"priority": 1, "metric_key": "kd_nM", "suggested_assay": "SPR", "reason": "fill gap"}],
                "blockers": [],
            }),
            evidence_ids_json="[]",
            is_superseded=0,
            created_at=now,
        )
    )
    db.commit()
    c = claims_svc.create_claim(
        db,
        scope_type="molecule",
        molecule_id=int(m.id),
        program_id=int(p.id),
        title=f"Claim {pid}",
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
        title=f"Plan {pid}",
        plan_type="readiness_advancement",
        status="recommended",
        expected_readiness_gain=1.0,
    )
    plans_svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment")
    return p, m, c, plan


def test_build_program_narrative_returns_structured_fields() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p, _m, _c, _plan = _seed_program(db, "P-narr", "narr")
            out = svc.build_program_narrative(db, program_id=int(p.id))
            assert int(out["program_id"]) == int(p.id)
            assert "scientific_thesis" in out
            assert "current_state_summary" in out
            assert "active_plans" in out
            assert "top_claims" in out
            assert "top_trajectory" in out
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_portfolio_narrative_returns_structured_fields() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            _seed_program(db, "P-narr-a", "a")
            _seed_program(db, "P-narr-b", "b")
            out = svc.build_portfolio_narrative(db)
            assert "portfolio_summary" in out
            assert "strongest_programs" in out
            assert "blocked_programs" in out
            assert "highest_value_plans" in out
            assert "task_burden_summary" in out
            assert "evidence_gap_summary" in out
        finally:
            db.close()
    finally:
        eng.dispose()


def test_program_thesis_and_milestone_synthesis_helpers() -> None:
    thesis = svc.synthesize_scientific_thesis(
        top_claims=[{"title": "Affinity claim", "claim_type": "affinity"}]
    )
    assert "Affinity claim" in thesis
    assert "affinity" in thesis.lower()

    state = svc.synthesize_current_state_summary(
        molecules_ready=1,
        molecules_missing_data=2,
        blocked_tasks=1,
        active_plans=3,
    )
    assert "1 molecules ready" in state
    assert "3 active plans" in state

    m1, r1, s1 = svc.synthesize_next_milestone(
        molecules_ready=1,
        top_trajectory_count=2,
        recommended_plan_count=1,
    )
    assert "Select lead molecule" in m1
    assert "trajectory opportunities" in r1
    assert s1 == "milestone_decision"


def test_support_uncertainty_risk_synthesis_helpers() -> None:
    sup = svc.synthesize_strongest_support(
        supported_claims=2,
        ready_molecules=1,
        active_plans=3,
    )
    unc = svc.synthesize_major_uncertainties(
        hypothesis_or_emerging_claims=4,
        missing_data_molecules=2,
        evidence_starved_claims=1,
    )
    risk = svc.synthesize_active_risks(
        contradicted_claims=1,
        overdue_tasks=2,
        blocked_tasks=3,
    )
    assert "Supported claims: 2" in sup
    assert "Evidence-starved claims: 1" in unc
    assert "Blocked tasks: 3" in risk


def test_confidence_and_maturity_rollup_helpers() -> None:
    claim_rollup = svc.build_claim_maturity_rollup(
        claim_summary={
            "supported": 2,
            "hypothesis_or_emerging": 1,
            "contradicted": 0,
            "evidence_starved": 1,
        }
    )
    evidence_rollup = svc.build_evidence_maturity_rollup(
        molecules_ready=1,
        molecules_missing_data=0,
    )
    plan_rollup = svc.build_plan_maturity_rollup(
        active_plans=3,
        recommended_plans=2,
        accepted_plans=1,
    )
    conf = svc.synthesize_confidence_summary(
        claim_rollup=claim_rollup,
        evidence_rollup=evidence_rollup,
        plan_rollup=plan_rollup,
    )
    assert claim_rollup["supported"] == 2
    assert evidence_rollup["ready_molecules"] == 1
    assert plan_rollup["recommended_plans"] == 2
    assert conf in {"high", "moderate", "developing"}


def test_program_narrative_includes_anchor_links() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p, _m, _c, _plan = _seed_program(db, "P-anchor", "anchor")
            out = svc.build_program_narrative(db, program_id=int(p.id))
            assert "narrative_links" in out
            assert "narrative_anchor_blocks" in out
            links = out["narrative_links"]
            assert isinstance(links.get("top_claim_links"), list)
            assert isinstance(links.get("top_plan_links"), list)
            assert isinstance(links.get("top_trajectory_links"), list)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_milestone_framing_helper_structure() -> None:
    out = svc.synthesize_milestone_framing(
        claim_rollup={"supported": 1, "hypothesis_or_emerging": 2},
        evidence_rollup={"ready_molecules": 1, "missing_data_molecules": 3},
        plan_rollup={"active_plans": 2, "recommended_plans": 1, "accepted_plans": 0},
    )
    assert "what_is_proven" in out
    assert "what_remains_to_prove" in out
    assert "what_would_unlock_next_milestone" in out
    assert "what_is_underway" in out


def test_portfolio_narrative_enrichment_fields() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            _seed_program(db, "P-narr-enrich-a", "na")
            _seed_program(db, "P-narr-enrich-b", "nb")
            out = svc.build_portfolio_narrative(db)
            assert "most_blocked_programs" in out
            assert "key_bottlenecks" in out
            assert "highest_value_plans" in out
            assert "near_term_inflection_rows" in out
            assert "leadership_cards" in out
            assert "programs_nearing_milestone" in out["leadership_cards"]
            assert isinstance(out["near_term_inflection_rows"], list)
        finally:
            db.close()
    finally:
        eng.dispose()
