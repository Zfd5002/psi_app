from __future__ import annotations

from datetime import datetime
import os
import tempfile

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, Molecule, Program
from psi.services.data_records import create_data_record


def _mkdb():
    fd, path = tempfile.mkstemp(prefix="psi_measurements_", suffix=".sqlite")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    with eng.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(data_measurements)").mappings().all()
        col_names = {str(r.get("name") or "") for r in cols}
        if "metric_key" not in col_names:
            conn.exec_driver_sql("ALTER TABLE data_measurements ADD COLUMN metric_key TEXT")
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp, path


def test_upsert_measurements_populates_name_and_metric_key_when_both_present() -> None:
    eng, SessionTmp, path = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 3, 0, 0, 0)
            p = Program(name="P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M1", title="Mol", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B1", title="Batch", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            rec = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Run",
                results_json={"ec50": 1.23},
            )
            rows = db.execute(
                text(
                    """
                    SELECT name, metric_key
                    FROM data_measurements
                    WHERE data_record_id = :rid
                    ORDER BY id ASC
                    """
                ),
                {"rid": int(rec.id)},
            ).mappings().all()
            assert len(rows) == 1
            assert str(rows[0].get("name") or "") == "ec50"
            assert str(rows[0].get("metric_key") or "") == "ec50"
        finally:
            db.close()
    finally:
        eng.dispose()
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
