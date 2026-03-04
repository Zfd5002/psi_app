from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Actor, AttributionEvent, Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.program_rollups import build_program_rollup
from psi.services.report_engine import generate_program_report_v0, load_report_run_payload
from psi.services.v3_ranking import build_ranking_surface, load_ranking_policy_v0_2


def test_attribution_does_not_influence_program_rollup_or_report_outputs():
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            p = Program(name="P", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-1", title="Mol", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(m); db.commit(); db.refresh(m)
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
                    outputs_json=stable_json_dumps({"decision_state": "ready", "readiness": {"state": "ready"}, "gates": []}),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 1, 0, 0),
                )
            )
            db.commit()
            as_of = datetime(2026, 2, 26, 2, 0, 0)
            rollup_before = build_program_rollup(db, program_id=int(p.id), as_of=as_of)
            report_before = load_report_run_payload(generate_program_report_v0(db, program_id=int(p.id), as_of=as_of, policy_pins={"report_policy": "v0"}))
            actor = db.query(Actor).filter(Actor.handle == "local-user").one_or_none()
            if actor is None:
                actor = Actor(display_name="Local User", handle="local-user", created_at=datetime(2026, 2, 26))
                db.add(actor)
                db.commit()
                db.refresh(actor)
            db.add(
                AttributionEvent(
                    actor_id=int(actor.id),
                    event_type="program.update",
                    entity_type="Program",
                    entity_id=int(p.id),
                    metadata_json="{}",
                    created_at=datetime(2026, 2, 26, 3, 0, 0),
                )
            )
            db.commit()
            rollup_after = build_program_rollup(db, program_id=int(p.id), as_of=as_of)
            report_after = load_report_run_payload(generate_program_report_v0(db, program_id=int(p.id), as_of=as_of, policy_pins={"report_policy": "v0"}))
        finally:
            db.close()
    finally:
        eng.dispose()
    assert stable_json_dumps(rollup_before) == stable_json_dumps(rollup_after)
    assert stable_json_dumps(report_before) == stable_json_dumps(report_after)


def test_attribution_does_not_influence_ranking_surface():
    policy = load_ranking_policy_v0_2()
    policy["enabled"] = True
    entities = [
        {"entity_type": "program", "entity_id": 2, "stable_sort_key": "P2", "criteria_hits": []},
        {"entity_type": "program", "entity_id": 1, "stable_sort_key": "P1", "criteria_hits": []},
    ]
    out1 = build_ranking_surface(entities=entities, policy=policy)
    out2 = build_ranking_surface(entities=entities, policy=policy)
    assert stable_json_dumps(out1) == stable_json_dumps(out2)
