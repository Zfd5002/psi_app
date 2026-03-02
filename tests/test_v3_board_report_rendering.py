from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.v3_board_reports import build_comparison_report_v3, build_molecule_report_v3, render_board_report_html


def test_v3_board_templates_render_for_molecule_and_comparison_reports() -> None:
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
                        outputs_json=stable_json_dumps({"decision_state": "ready", "readiness": {"state": "ready"}}),
                        evidence_ids_json="[]",
                        created_at=datetime(2026, 2, 26, 0, 0, 0),
                    )
                )
            db.commit()
            mol_payload = build_molecule_report_v3(db, molecule_id=int(m1.id), as_of=datetime(2026, 2, 27, 0, 0, 0))
            cmp_payload = build_comparison_report_v3(db, molecule_ids=[int(m1.id), int(m2.id)], as_of=datetime(2026, 2, 27, 0, 0, 0))
        finally:
            db.close()
    finally:
        eng.dispose()

    mol_html = render_board_report_html(report_payload=mol_payload)
    cmp_html = render_board_report_html(report_payload=cmp_payload)
    assert "I Governance Header" in mol_html
    assert "I Governance Header" in cmp_html
    assert "VIII Executive Summary Bullets" in mol_html
    assert "VIII Executive Summary Bullets" in cmp_html

