from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services.programs import list_program_molecule_statuses, upsert_program_molecule_status


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_program_molecule_status_upsert_and_list_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-status", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m1 = Molecule(program_id=int(p.id), primary_id="M-A", title="A", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p.id), primary_id="M-B", title="B", created_at=now, updated_at=now)
            db.add_all([m1, m2])
            db.commit()
            db.refresh(m1)
            db.refresh(m2)

            upsert_program_molecule_status(
                db,
                program_id=int(p.id),
                molecule_id=int(m2.id),
                role="backup",
                rationale="secondary candidate",
            )
            upsert_program_molecule_status(
                db,
                program_id=int(p.id),
                molecule_id=int(m1.id),
                role="lead",
                rationale="best overall coverage",
            )
            # invalid roles are normalized deterministically
            upsert_program_molecule_status(
                db,
                program_id=int(p.id),
                molecule_id=int(m2.id),
                role="invalid_role",
                rationale="normalize to active",
            )

            rows = list_program_molecule_statuses(db, program_id=int(p.id))
            assert [int(r.molecule_id) for r in rows] == sorted([int(m1.id), int(m2.id)])
            by_mid = {int(r.molecule_id): r for r in rows}
            assert str(by_mid[int(m1.id)].role) == "lead"
            assert str(by_mid[int(m2.id)].role) == "active"
            assert str(by_mid[int(m2.id)].rationale or "") == "normalize to active"
        finally:
            db.close()
    finally:
        eng.dispose()

