from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import (
    Base,
    DataRecord,
    DecisionSnapshot,
    ExperimentTask,
    Molecule,
    Program,
)
from psi.services import claims as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_create_and_list_for_molecule_program() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-claims", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claims", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c1 = svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Affinity hypothesis",
                claim_type="affinity",
                statement="",
            )
            c2 = svc.create_claim(
                db,
                scope_type="program",
                molecule_id=None,
                program_id=int(p.id),
                title="Program readiness claim",
                claim_type="in_vivo_readiness",
                statement="Program is ready for in vivo advancement.",
                status="emerging",
                confidence_level="medium",
            )
            by_m = svc.list_claims_for_molecule(db, molecule_id=int(m.id))
            by_p = svc.list_claims_for_program(db, program_id=int(p.id))
            assert [int(x.id) for x in by_m] == [int(c1.id)]
            assert {int(x.id) for x in by_p} == {int(c1.id), int(c2.id)}
            assert str(c1.statement).startswith("[affinity]")
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claim_status_transitions_and_archive() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-claims-st", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claims-st", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Claim",
                claim_type="affinity",
                statement="x",
            )
            c = svc.update_claim_status(db, claim_id=int(c.id), status="emerging")
            assert str(c.status) == "emerging"
            assert svc.can_transition_claim_status(from_status="emerging", to_status="supported") is True
            assert svc.can_transition_claim_status(from_status="supported", to_status="emerging") is False
            c = svc.update_claim_status(db, claim_id=int(c.id), status="supported")
            assert str(c.status) == "supported"
            c = svc.archive_claim(db, claim_id=int(c.id))
            assert str(c.status) == "archived"
            try:
                svc.update_claim_status(db, claim_id=int(c.id), status="emerging")
                assert False, "expected invalid transition"
            except ValueError:
                pass
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claim_transition_matrix_enforces_terminal_archived() -> None:
    assert svc.can_transition_claim_status(from_status="hypothesis", to_status="emerging") is True
    assert svc.can_transition_claim_status(from_status="hypothesis", to_status="supported") is False
    assert svc.can_transition_claim_status(from_status="emerging", to_status="contradicted") is True
    assert svc.can_transition_claim_status(from_status="supported", to_status="archived") is True
    assert svc.can_transition_claim_status(from_status="archived", to_status="hypothesis") is False


def test_claim_ordering_prefers_status_then_confidence_then_updated() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-claims-ord", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claims-ord", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c1 = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="A", claim_type="affinity", statement="x", status="hypothesis", confidence_level="high")
            c2 = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="B", claim_type="affinity", statement="x", status="emerging", confidence_level="low")
            c3 = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="C", claim_type="affinity", statement="x", status="supported", confidence_level="high")
            rows = svc.list_claims_for_molecule(db, molecule_id=int(m.id), include_archived=True)
            assert [int(r.id) for r in rows] == [int(c2.id), int(c1.id), int(c3.id)]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claim_type_discipline_and_helpers() -> None:
    assert svc.normalize_claim_type("affinity") == "affinity"
    assert svc.normalize_claim_type("unknown") == "mechanism"
    assert svc.claim_type_template("affinity").startswith("Molecule exhibits target affinity")
    assert "[manufacturability] Scale-up." in svc.format_claim_statement(claim_type="manufacturability", title="Scale-up", statement="")


def test_claim_linking_and_summaries() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-claims-link", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claims-link", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Aff claim", claim_type="affinity", statement="x", status="emerging")
            r1 = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="Biological", data_type="Binding", method="BLI", title="r1", created_at=now, updated_at=now)
            r2 = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="Biological", data_type="Binding", method="SPR", title="r2", created_at=now, updated_at=now)
            t1 = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now, updated_at=now)
            t2 = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="done", created_at=now, updated_at=now)
            snap = DecisionSnapshot(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json="{}", evidence_ids_json="[]", is_superseded=0, created_at=now)
            db.add_all([r1, r2, t1, t2, snap]); db.commit(); db.refresh(r1); db.refresh(r2); db.refresh(t1); db.refresh(t2); db.refresh(snap)
            svc.link_claim_to_data_record(db, claim_id=int(c.id), data_record_id=int(r1.id), direction="supporting")
            svc.link_claim_to_data_record(db, claim_id=int(c.id), data_record_id=int(r2.id), direction="contradicting")
            svc.link_claim_to_decision(db, claim_id=int(c.id), decision_snapshot_id=int(snap.id), relationship_type="informs")
            svc.link_claim_to_task(db, claim_id=int(c.id), experiment_task_id=int(t1.id), relationship_type="tests")
            svc.link_claim_to_task(db, claim_id=int(c.id), experiment_task_id=int(t2.id), relationship_type="tests")
            s1 = svc.summarize_claim_support(db, claim_id=int(c.id))
            s2 = svc.summarize_claim_conflict(db, claim_id=int(c.id))
            s3 = svc.summarize_claim_maturity(db, claim_id=int(c.id))
            assert s1["supporting_count"] == 1
            assert s1["contradicting_count"] == 1
            assert s2["has_conflict"] is True
            assert s3["linked_decisions_count"] == 1
            assert s3["linked_tasks_open"] == 1
            assert s3["linked_tasks_done"] == 1
            assert svc.unlink_claim_from_data_record(db, claim_id=int(c.id), data_record_id=int(r2.id), direction="contradicting") == 1
        finally:
            db.close()
    finally:
        eng.dispose()
