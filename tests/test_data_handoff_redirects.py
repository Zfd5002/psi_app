from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, Molecule, Program
from psi.web.routers import data_records as data_records_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_create_data_redirects_with_handoff_query_when_task_linked() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-handoff-redirect", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-HR", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-HR", title="b", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            resp = data_records_router.create_data(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Task-linked run",
                task_id=None,
                return_to="/programs/1/workflow",
                notes="",
                run_date="2026-03-08",
                params_json="{}",
                results_json="{\"kd_nM\": 4.1}",
                files=[],
                db=db,
                storage=None,
            )
            assert resp.status_code == 303
            assert "return_to=%2Fprograms%2F1%2Fworkflow" in str(resp.headers.get("location") or "")
        finally:
            db.close()
    finally:
        eng.dispose()

