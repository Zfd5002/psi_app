from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, ExperimentTask, Molecule, Program
from psi.services import claims as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_task_link_keeps_task_state_unchanged() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-clt", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-clt", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            t = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now, updated_at=now)
            db.add(t); db.commit(); db.refresh(t)
            status_before = str(t.status)
            c = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Claim", claim_type="mechanism", statement="x")
            svc.link_claim_to_task(db, claim_id=int(c.id), experiment_task_id=int(t.id), relationship_type="tests")
            rows = svc.list_claim_tasks(db, claim_id=int(c.id))
            assert len(rows) == 1
            assert int(rows[0].experiment_task_id) == int(t.id)
            db.refresh(t)
            assert str(t.status) == status_before
        finally:
            db.close()
    finally:
        eng.dispose()
