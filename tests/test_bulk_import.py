from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, Molecule, Program
from psi.services.bulk_import import parse_bulk_import_rows, validate_bulk_import_rows


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_parse_bulk_import_rows_requires_header() -> None:
    try:
        parse_bulk_import_rows("bad,header\nx,y")
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_validate_bulk_import_rows_returns_rows_and_errors_deterministically() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-bulk", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-BULK", title="bulk", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-1", title="", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            rows = parse_bulk_import_rows(
                "molecule,batch,metric,value,unit\n"
                "M-BULK,B-1,monomer_pct,88,%\n"
                "M-BULK,B-1,kd_nM,abc,nM\n"
            )
            out = validate_bulk_import_rows(db, parsed_rows=rows)
            assert len(out["validated_rows"]) == 1
            assert out["validated_rows"][0]["metric_key"] == "monomer_pct"
            assert len(out["errors"]) == 1
            assert "not numeric" in out["errors"][0]["error"]
        finally:
            db.close()
    finally:
        eng.dispose()

