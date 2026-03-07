from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.measurement_schema import measurement_cols
from psi.core.models import Base, DataRecord, Molecule, Program
from psi.services.trends import build_molecule_trends


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_molecule_trends_returns_deterministic_time_series() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-trend", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-trend", title="Trend", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            r1 = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                domain="CMC",
                data_type="CMC_Analytics",
                method="SEC_HPLC",
                title="R1",
                run_date="2026-03-01",
                created_at=now,
                updated_at=now,
            )
            r2 = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="R2",
                run_date="2026-03-02",
                created_at=now,
                updated_at=now,
            )
            db.add_all([r1, r2])
            db.commit()
            db.refresh(r1)
            db.refresh(r2)

            cols = measurement_cols(db)
            db.execute(
                text(
                    f"""
                    INSERT INTO data_measurements ({cols['record_fk']}, {cols['name']}, {cols['value_num']}, {cols['created_at']})
                    VALUES (:rid, :mk, :val, :ts)
                    """
                ),
                [
                    {"rid": int(r1.id), "mk": "monomer_pct", "val": 83.0, "ts": "2026-03-01"},
                    {"rid": int(r2.id), "mk": "kd_nM", "val": 9.0, "ts": "2026-03-02"},
                ],
            )
            db.commit()

            out = build_molecule_trends(db, molecule_id=int(m.id))
            assert out["metric_keys"] == ["monomer_pct", "kd_nM", "value_eu_ml"]
            assert [x["value"] for x in out["series"]["monomer_pct"]] == [83.0]
            assert [x["value"] for x in out["series"]["kd_nM"]] == [9.0]
            assert out["series"]["value_eu_ml"] == []
        finally:
            db.close()
    finally:
        eng.dispose()

