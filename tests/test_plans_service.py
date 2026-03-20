from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program, ScientificClaim
from psi.services import plans as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_plan_create_list_and_get_for_scopes() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plans", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plans", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = ScientificClaim(
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Claim",
                claim_type="affinity",
                statement="x",
                status="hypothesis",
                confidence_level="low",
                created_at=now,
                updated_at=now,
            )
            db.add(c); db.commit(); db.refresh(c)

            pm = svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Molecule plan",
                plan_type="readiness_advancement",
                status="recommended",
                expected_readiness_gain=1.0,
            )
            pc = svc.create_plan(
                db,
                scope_type="claim",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=int(c.id),
                title="Claim plan",
                plan_type="claim_de_risking",
                status="draft",
                expected_claim_support_gain=0.8,
            )
            pp = svc.create_plan(
                db,
                scope_type="program",
                molecule_id=None,
                program_id=int(p.id),
                claim_id=None,
                title="Program plan",
                plan_type="evidence_completion",
                status="accepted",
                expected_evidence_coverage_gain=0.5,
            )
            assert int(svc.get_plan(db, plan_id=int(pm.id)).id) == int(pm.id)
            assert {int(x.id) for x in svc.list_plans_for_molecule(db, molecule_id=int(m.id), include_archived=True)} == {int(pm.id), int(pc.id)}
            assert {int(x.id) for x in svc.list_plans_for_claim(db, claim_id=int(c.id), include_archived=True)} == {int(pc.id)}
            assert {int(x.id) for x in svc.list_plans_for_program(db, program_id=int(p.id), include_archived=True)} == {int(pm.id), int(pc.id), int(pp.id)}
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_archive_supersede_and_top_helpers() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plans-status", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plans-status", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            p1 = svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="A", plan_type="readiness_advancement", status="recommended", expected_readiness_gain=1.0)
            p2 = svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="B", plan_type="readiness_advancement", status="draft", expected_readiness_gain=0.2)
            svc.archive_plan(db, plan_id=int(p2.id))
            rows = svc.top_plans_for_molecule(db, molecule_id=int(m.id), limit=10)
            assert [int(r.id) for r in rows] == [int(p1.id)]
            svc.supersede_plan(db, plan_id=int(p1.id))
            assert svc.top_plans_for_molecule(db, molecule_id=int(m.id), limit=10) == []
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_and_step_transition_matrix_and_ordering() -> None:
    assert svc.can_transition_plan_status(from_status="draft", to_status="recommended") is True
    assert svc.can_transition_plan_status(from_status="accepted", to_status="recommended") is False
    assert svc.can_transition_step_status(from_status="proposed", to_status="task_created") is True
    assert svc.can_transition_step_status(from_status="done", to_status="proposed") is False

    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-transition", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-transition", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan",
                plan_type="readiness_advancement",
                status="draft",
            )
            plan = svc.update_plan_status(db, plan_id=int(plan.id), status="recommended")
            assert str(plan.status) == "recommended"
            plan = svc.update_plan_status(db, plan_id=int(plan.id), status="accepted")
            assert str(plan.status) == "accepted"
            try:
                svc.update_plan_status(db, plan_id=int(plan.id), status="draft")
                assert False, "expected invalid transition"
            except ValueError:
                pass
            s1 = svc.add_plan_step(db, plan_id=int(plan.id), step_order=1, step_kind="experiment", status="proposed")
            s2 = svc.add_plan_step(db, plan_id=int(plan.id), step_order=2, step_kind="experiment", status="task_created")
            rows = svc.list_plan_steps(db, plan_id=int(plan.id))
            assert [int(x.id) for x in rows] == [int(s1.id), int(s2.id)]
            svc.update_plan_step_status(db, step_id=int(s1.id), status="task_created")
            svc.update_plan_step_status(db, step_id=int(s1.id), status="done")
            try:
                svc.update_plan_step_status(db, step_id=int(s1.id), status="proposed")
                assert False, "expected invalid transition"
            except ValueError:
                pass
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_step_operations() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-steps", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-steps", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan",
                plan_type="evidence_completion",
                status="recommended",
            )
            s1 = svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment")
            s2 = svc.add_plan_step(db, plan_id=int(plan.id), metric_key="sec_monomer_pct", suggested_assay="SEC", step_kind="confirmatory")
            rows = svc.list_plan_steps(db, plan_id=int(plan.id))
            assert [int(x.id) for x in rows] == [int(s1.id), int(s2.id)]
            assert [int(x.step_order) for x in rows] == [1, 2]
            s1 = svc.update_plan_step_status(db, step_id=int(s1.id), status="task_created")
            assert str(s1.status) == "task_created"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_list_plan_steps_for_plan_ids_groups_and_orders_per_plan() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-plan-batch-steps", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-plan-batch-steps", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan_a = svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan A",
                plan_type="readiness_advancement",
                status="recommended",
            )
            plan_b = svc.create_plan(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                claim_id=None,
                title="Plan B",
                plan_type="readiness_advancement",
                status="recommended",
            )
            b_done = svc.add_plan_step(db, plan_id=int(plan_b.id), step_order=1, step_kind="experiment", status="done")
            a_task_created = svc.add_plan_step(db, plan_id=int(plan_a.id), step_order=2, step_kind="experiment", status="task_created")
            a_proposed = svc.add_plan_step(db, plan_id=int(plan_a.id), step_order=1, step_kind="experiment", status="proposed")
            rows_by_plan = svc.list_plan_steps_for_plan_ids(db, plan_ids=[int(plan_b.id), int(plan_a.id)])
            assert sorted(rows_by_plan.keys()) == [int(plan_a.id), int(plan_b.id)]
            assert [int(x.id) for x in rows_by_plan[int(plan_a.id)]] == [int(a_proposed.id), int(a_task_created.id)]
            assert [int(x.id) for x in rows_by_plan[int(plan_b.id)]] == [int(b_done.id)]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plan_type_and_step_kind_discipline_helpers() -> None:
    assert svc.normalize_plan_type("claim_de_risking") == "claim_de_risking"
    assert svc.normalize_plan_type("unknown") == "readiness_advancement"
    assert svc.normalize_step_kind("confirmatory") == "confirmatory"
    assert svc.normalize_step_kind("bad") == "experiment"
    assert svc.plan_type_template("evidence_completion").startswith("Complete missing evidence")
    text = svc.format_plan_rationale(plan_type="developability_followup", title="Dev plan", rationale="")
    assert text.startswith("[developability_followup] Dev plan.")
