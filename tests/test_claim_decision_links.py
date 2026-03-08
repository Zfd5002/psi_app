from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.services import claims as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_decision_link_is_link_only() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-cld", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-cld", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            snap = DecisionSnapshot(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json='{"decision_state":"ready"}', evidence_ids_json="[]", is_superseded=0, created_at=now)
            db.add(snap); db.commit(); db.refresh(snap)
            outputs_before = str(snap.outputs_json)
            c = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Readiness", claim_type="in_vivo_readiness", statement="x")
            svc.link_claim_to_decision(db, claim_id=int(c.id), decision_snapshot_id=int(snap.id), relationship_type="informs")
            rows = svc.list_claim_decisions(db, claim_id=int(c.id))
            assert len(rows) == 1
            assert int(rows[0].decision_snapshot_id) == int(snap.id)
            db.refresh(snap)
            assert str(snap.outputs_json) == outputs_before
        finally:
            db.close()
    finally:
        eng.dispose()
