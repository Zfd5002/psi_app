from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
import copy

from psi.services.v3_board_reports import (
    SECTION_ORDER,
    build_comparison_report_v3,
    build_molecule_report_v3,
    canonical_v3_report_json,
)


def test_v3_board_report_json_is_deterministic_and_timestamp_excluded_from_fingerprint() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            p = Program(name="P")
            db.add(p)
            db.flush()
            m1 = Molecule(program_id=int(p.id), primary_id="M1", title="Mol 1")
            m2 = Molecule(program_id=int(p.id), primary_id="M2", title="Mol 2")
            db.add_all([m1, m2])
            db.flush()
            out = {
                "decision_state": "ready",
                "readiness": {"state": "ready"},
                "state_of_evidence": {"soe_v0_2": {"coverage": {"coverage_ratio": 1.0e-06}}},
                "comparability": {"summary": {"high_severity_count": 0, "total_flags": 0}},
            }
            for mid in (int(m1.id), int(m2.id)):
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
                        outputs_json=stable_json_dumps(out),
                        evidence_ids_json="[]",
                        created_at=datetime(2026, 2, 26, 0, 0, 0),
                    )
                )
            db.commit()
            a = build_molecule_report_v3(db, molecule_id=int(m1.id), as_of=datetime(2026, 2, 27, 0, 0, 0), report_timestamp="A")
            b = build_molecule_report_v3(db, molecule_id=int(m1.id), as_of=datetime(2026, 2, 27, 0, 0, 0), report_timestamp="B")
            c1 = build_comparison_report_v3(db, molecule_ids=[int(m2.id), int(m1.id)], as_of=datetime(2026, 2, 27, 0, 0, 0), report_timestamp="A")
            c2 = build_comparison_report_v3(db, molecule_ids=[int(m1.id), int(m2.id)], as_of=datetime(2026, 2, 27, 0, 0, 0), report_timestamp="B")
        finally:
            db.close()
    finally:
        eng.dispose()

    assert a["sections"]["I_governance_header"]["report_fingerprint"] == b["sections"]["I_governance_header"]["report_fingerprint"]
    assert list(a["sections"].keys()) == SECTION_ORDER
    assert list(c1["sections"].keys()) == SECTION_ORDER
    assert [x["molecule_id"] for x in c1["sections"]["II_general_profile"]["columns"]] == [x["molecule_id"] for x in c2["sections"]["II_general_profile"]["columns"]]
    c1_basis = copy.deepcopy(c1)
    c2_basis = copy.deepcopy(c2)
    c1_basis["sections"]["I_governance_header"]["report_timestamp"] = None
    c2_basis["sections"]["I_governance_header"]["report_timestamp"] = None
    assert canonical_v3_report_json(c1_basis) == canonical_v3_report_json(c2_basis)
    assert "e-" not in canonical_v3_report_json(a).lower()
    assert "e+" not in canonical_v3_report_json(a).lower()
