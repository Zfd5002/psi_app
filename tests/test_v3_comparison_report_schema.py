from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.v3_board_reports import SECTION_ORDER, build_comparison_report_v3


def test_v3_comparison_report_schema_order_and_column_sorting() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            p = Program(name="P")
            db.add(p)
            db.flush()
            m2 = Molecule(program_id=int(p.id), primary_id="M2", title="Mol 2")
            m1 = Molecule(program_id=int(p.id), primary_id="M1", title="Mol 1")
            db.add_all([m2, m1])
            db.flush()
            for mid, state in ((int(m2.id), "not_ready"), (int(m1.id), "ready")):
                db.add(
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=int(mid),
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v0.5",
                        engine_key="di",
                        schema_version="di.snapshot.v0_4",
                        inputs_json=stable_json_dumps({"engine_key": "di"}),
                        outputs_json=stable_json_dumps({"decision_state": state, "readiness": {"state": state}}),
                        evidence_ids_json="[]",
                        created_at=datetime(2026, 2, 26, 0, 0, 0),
                    )
                )
            db.commit()
            rpt = build_comparison_report_v3(
                db,
                molecule_ids=[int(m2.id), int(m1.id)],
                as_of=datetime(2026, 2, 27, 0, 0, 0),
                report_timestamp="2026-03-02T15:00:00Z",
            )
        finally:
            db.close()
    finally:
        eng.dispose()

    assert list(rpt["sections"].keys()) == SECTION_ORDER
    cols = rpt["sections"]["II_general_profile"]["columns"]
    assert [int(c["molecule_id"]) for c in cols] == sorted([int(c["molecule_id"]) for c in cols])
    assert len(rpt["sections"]["IV_in_vitro_evidence_tables"]["rows"]) >= 2

