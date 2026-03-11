from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, Molecule, Program
from psi.services import qc as qc_svc
from psi.services.data_records import apply_bulk_qc_action_for_record, create_data_record, update_data_record
from psi.services.measurements import list_measurements_for_record


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_bulk_approve_record_applies_to_all_measurements_idempotently() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P1", description="", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M1", title="Mol1", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B1", title="Batch 1", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
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
                title="Binding run",
                results_json={"ec50": 12.3, "kd": 45.6},
            )
            mids = [int(x.get("id")) for x in list_measurements_for_record(db, record_id=int(rec.id)) if x.get("id") is not None]
            assert len(mids) == 2

            out1 = apply_bulk_qc_action_for_record(db, record_id=int(rec.id), action="approve", actor="scientist")
            assert out1["measurement_count"] == 2
            assert out1["applied_count"] == 2
            states1 = qc_svc.get_qc_state_for_measurements(db, mids)
            assert all(str(states1[mid]["status"]) == "approved" for mid in mids)

            out2 = apply_bulk_qc_action_for_record(db, record_id=int(rec.id), action="approve", actor="scientist")
            assert out2["applied_count"] == 0
            assert out2["skipped_count"] == 2
        finally:
            db.close()
    finally:
        eng.dispose()


def test_update_data_record_derives_run_date_from_run_at() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P2", description="", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M2", title="Mol2", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(m); db.commit(); db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B2", title="Batch 2", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(b); db.commit(); db.refresh(b)
            rec = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Init",
                results_json={"ec50": 9.9},
            )
            out = update_data_record(
                db,
                record_id=int(rec.id),
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Updated",
                run_date="",
                run_at="2026-03-03T10:11:12",
                params_json={},
                results_json={"ec50": 10.1},
            )
            assert str(out.run_date or "") == "2026-03-03"
        finally:
            db.close()
    finally:
        eng.dispose()
