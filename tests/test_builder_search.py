from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.web.routers.builder import _search_builder_molecules


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_builder_search_returns_primary_title_and_program_name_with_limit() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Prog-A", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            for idx in range(12):
                aa = chr(ord("A") + (idx % 20))
                bb = chr(ord("C") + (idx % 20))
                molecule_svc.create_molecule(
                    db,
                    program_id=int(p.id),
                    primary_id=f"MB-{idx:02d}",
                    title=f"Builder Molecule {idx:02d}",
                    components={"HC1": f"AAAA{aa}", "LC1": f"BBBB{bb}"},
                )
            rows = _search_builder_molecules(db, q="MB-", limit=10)
            assert len(rows) == 10
            assert set(rows[0].keys()) == {"id", "primary_id", "title", "program_name"}
            assert rows[0]["program_name"] == "Prog-A"
        finally:
            db.close()
    finally:
        eng.dispose()
