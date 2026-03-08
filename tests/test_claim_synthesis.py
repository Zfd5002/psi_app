from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services import claims as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_synthesis_support_conflict_and_maturity() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-cls", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-cls", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Claim", claim_type="developability", statement="x", status="supported")
            r1 = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="CMC", data_type="CMC_Analytics", method="SEC_HPLC", title="r1", created_at=now, updated_at=now)
            r2 = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="CMC", data_type="CMC_Analytics", method="SEC_HPLC", title="r2", created_at=now, updated_at=now)
            t1 = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="done", created_at=now, updated_at=now)
            t2 = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="in_progress", created_at=now, updated_at=now)
            snap = DecisionSnapshot(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json="{}", evidence_ids_json="[]", is_superseded=0, created_at=now)
            db.add_all([r1, r2, t1, t2, snap]); db.commit(); db.refresh(r1); db.refresh(r2); db.refresh(t1); db.refresh(t2); db.refresh(snap)
            svc.link_claim_to_data_record(db, claim_id=int(c.id), data_record_id=int(r1.id), direction="supporting")
            svc.link_claim_to_data_record(db, claim_id=int(c.id), data_record_id=int(r2.id), direction="contradicting")
            svc.link_claim_to_decision(db, claim_id=int(c.id), decision_snapshot_id=int(snap.id), relationship_type="reflects")
            svc.link_claim_to_task(db, claim_id=int(c.id), experiment_task_id=int(t1.id), relationship_type="tests")
            svc.link_claim_to_task(db, claim_id=int(c.id), experiment_task_id=int(t2.id), relationship_type="tests")
            support = svc.summarize_claim_support(db, claim_id=int(c.id))
            conflict = svc.summarize_claim_conflict(db, claim_id=int(c.id))
            maturity = svc.summarize_claim_maturity(db, claim_id=int(c.id))
            assert support["supporting_count"] == 1
            assert support["contradicting_count"] == 1
            assert conflict["has_conflict"] is True
            assert maturity["linked_decisions_count"] == 1
            assert maturity["linked_tasks_open"] == 1
            assert maturity["linked_tasks_done"] == 1
            assert maturity["maturity_summary"] in {"supported", "contradicted", "emerging", "hypothesis"}
        finally:
            db.close()
    finally:
        eng.dispose()
