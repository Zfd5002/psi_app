from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.template_ladder_report import build_template_ladder_report, render_template_ladder_report_html


def test_template_ladder_report_schema_and_rendering_are_deterministic() -> None:
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
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v0.5",
                    engine_key="di",
                    schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps({"decision_state": "not_ready", "readiness": {"state": "not_ready"}, "gate_outcomes": {}}),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 0, 0, 0),
                )
            )
            db.commit()
            r1 = build_template_ladder_report(db, molecule_id=int(m.id), as_of=datetime(2026, 2, 27, 0, 0, 0))
            r2 = build_template_ladder_report(db, molecule_id=int(m.id), as_of=datetime(2026, 2, 27, 0, 0, 0))
        finally:
            db.close()
    finally:
        eng.dispose()

    assert stable_json_dumps(r1) == stable_json_dumps(r2)
    assert r1["schema_id"] == "template_ladder_report_v3"
    assert "stage_table" in r1 and "missing_prerequisites_table" in r1 and "next_actions_bullets" in r1
    html = render_template_ladder_report_html(report_payload=r1)
    assert "Template Ladder Header" in html
    assert "Stage Table" in html

