from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Molecule, Program
from psi.services import report_engine
from psi.services import reports_v3


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_generate_report_from_form_invokes_ack_guard_once(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P1", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-1", title="Mol1", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(m)
            db.commit()
            db.refresh(m)

            call_count = {"n": 0}

            def _guard_once(db, *, current_policy_pins, action):
                call_count["n"] += 1
                return action()

            monkeypatch.setattr(report_engine, "run_semantic_action_with_ack_guard", _guard_once)

            row = reports_v3.generate_report_from_form(
                db,
                report_type="molecule_report",
                subject_ids_text=str(int(m.id)),
                as_of_text="2026-02-26T02:00:00Z",
            )
            assert int(row.id) > 0
            assert call_count["n"] == 1
        finally:
            db.close()
    finally:
        eng.dispose()
