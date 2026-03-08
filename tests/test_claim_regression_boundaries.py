from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services import claims as claims_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_reads_do_not_mutate_di_snapshots_or_tasks_or_evidence() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-crb", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-crb", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            snap = DecisionSnapshot(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state": "not_ready"}), evidence_ids_json="[]", is_superseded=0, created_at=now)
            task = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now, updated_at=now)
            db.add_all([snap, task]); db.commit(); db.refresh(snap); db.refresh(task)
            c = claims_svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Claim", claim_type="affinity", statement="x", status="emerging")
            outputs_before = str(snap.outputs_json)
            task_status_before = str(task.status)
            data_count_before = int(db.query(DataRecord).count())

            _ = claims_svc.get_claim_detail(db, claim_id=int(c.id))
            _ = claims_svc.summarize_claim_maturity(db, claim_id=int(c.id))
            _ = claims_svc.top_claims_for_molecule(db, molecule_id=int(m.id), limit=5)

            db.refresh(snap); db.refresh(task)
            assert str(snap.outputs_json) == outputs_before
            assert str(task.status) == task_status_before
            assert int(db.query(DataRecord).count()) == data_count_before
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claim_ordering_and_summaries_are_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-crb2", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-crb2", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c1 = claims_svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="A", claim_type="affinity", statement="x", status="emerging", confidence_level="high")
            c2 = claims_svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="B", claim_type="affinity", statement="x", status="hypothesis", confidence_level="low")
            a = [int(x.id) for x in claims_svc.list_claims_for_molecule(db, molecule_id=int(m.id), include_archived=True)]
            b = [int(x.id) for x in claims_svc.list_claims_for_molecule(db, molecule_id=int(m.id), include_archived=True)]
            assert a == b
            assert set(a) == {int(c1.id), int(c2.id)}
            s1 = claims_svc.summarize_claim_support(db, claim_id=int(c1.id))
            s2 = claims_svc.summarize_claim_support(db, claim_id=int(c1.id))
            assert s1 == s2
        finally:
            db.close()
    finally:
        eng.dispose()
