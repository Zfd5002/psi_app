from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.v3_board_reports import SECTION_ORDER, build_molecule_report_v3


def test_v3_molecule_report_schema_order_and_fingerprint_excludes_timestamp() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            p = Program(name="P")
            db.add(p)
            db.flush()
            m = Molecule(program_id=int(p.id), primary_id="M1", title="Mol 1")
            db.add(m)
            db.flush()
            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v0.5",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps(
                    {
                        "decision_state": "ready",
                        "readiness": {"state": "ready"},
                        "policy": {"policy_id": "advance_to_in_vivo", "policy_version": "v0.5"},
                    }
                ),
                evidence_ids_json="[]",
                created_at=datetime(2026, 2, 26, 0, 0, 0),
            )
            db.add(snap)
            db.commit()
            r1 = build_molecule_report_v3(
                db,
                molecule_id=int(m.id),
                as_of=datetime(2026, 2, 27, 0, 0, 0),
                report_timestamp="2026-03-02T14:00:00Z",
            )
            r2 = build_molecule_report_v3(
                db,
                molecule_id=int(m.id),
                as_of=datetime(2026, 2, 27, 0, 0, 0),
                report_timestamp="2026-03-02T15:00:00Z",
            )
        finally:
            db.close()
    finally:
        eng.dispose()

    assert list(r1["sections"].keys()) == SECTION_ORDER
    assert r1["sections"]["I_governance_header"]["report_fingerprint"] == r2["sections"]["I_governance_header"]["report_fingerprint"]
    assert r1["sections"]["I_governance_header"]["report_timestamp"] != r2["sections"]["I_governance_header"]["report_timestamp"]

