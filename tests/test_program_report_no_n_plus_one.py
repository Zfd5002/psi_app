from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services import report_engine


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_generate_program_report_avoids_report_engine_snapshot_refetch(monkeypatch) -> None:
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
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="vX",
                    engine_key="di",
                    schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps({"decision_state": "ready", "readiness": {"state": "ready"}, "gates": [], "used_by_metric": {"ec50": [1]}}),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 1, 0, 0),
                )
            )
            db.commit()

            def _should_not_be_called(*args, **kwargs):
                raise AssertionError("report_engine._latest_di_snapshot_for_molecule_as_of should not be called in program report path")

            monkeypatch.setattr(report_engine, "_latest_di_snapshot_for_molecule_as_of", _should_not_be_called)

            row = report_engine.generate_program_report_v0(
                db,
                program_id=int(p.id),
                as_of=datetime(2026, 2, 26, 2, 0, 0),
                policy_pins={"report_policy": "v0"},
            )
            assert int(row.id) > 0
        finally:
            db.close()
    finally:
        eng.dispose()
