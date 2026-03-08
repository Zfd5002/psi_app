from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, Molecule, Program
from psi.services import claims as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_evidence_linking_and_unlinking() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-cle", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-cle", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="Affinity", claim_type="affinity", statement="x")
            r = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="Biological", data_type="Binding", method="BLI", title="r", created_at=now, updated_at=now)
            db.add(r); db.commit(); db.refresh(r)
            svc.link_claim_to_data_record(db, claim_id=int(c.id), data_record_id=int(r.id), direction="supporting")
            rows = svc.list_claim_evidence(db, claim_id=int(c.id))
            assert len(rows) == 1
            assert str(rows[0].direction) == "supporting"
            assert svc.unlink_claim_from_data_record(db, claim_id=int(c.id), data_record_id=int(r.id), direction="supporting") == 1
            assert svc.list_claim_evidence(db, claim_id=int(c.id)) == []
        finally:
            db.close()
    finally:
        eng.dispose()
