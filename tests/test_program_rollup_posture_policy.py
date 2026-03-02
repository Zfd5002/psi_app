from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program, ProgramMembership
from psi.core.utils import stable_json_dumps
from psi.services.program_rollups import build_program_rollup


def _collect_keys(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(str(k))
            _collect_keys(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _collect_keys(x, out)


def test_program_rollup_policy_catalog_v0_1_loads_and_is_ordered() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "core" / "di" / "catalogs" / "program_rollup_policy_v0_1.json"
    pol = json.loads(root.read_text(encoding="utf-8"))
    assert str(pol.get("policy_id") or "") == "program_rollup_policy_v0_1"
    assert str(pol.get("policy_version") or "") == "v0.1"
    assert pol.get("posture_states") == ["insufficient_evidence", "blocked", "at_risk", "on_track"]
    rules = pol.get("rule_order") if isinstance(pol.get("rule_order"), list) else []
    assert [str((r or {}).get("id") or "") for r in rules] == [
        "rule_insufficient_evidence",
        "rule_blocked",
        "rule_on_track",
        "rule_at_risk_fallback",
    ]


def test_program_rollup_posture_payload_is_deterministic_and_has_no_banned_keys() -> None:
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
            db.add(ProgramMembership(program_id=int(p.id), molecule_id=int(m.id), sort_index=1))
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
                    outputs_json=stable_json_dumps({"decision_state": "ready", "gates": []}),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 0, 0, 0),
                )
            )
            db.commit()
            r1 = build_program_rollup(db, program_id=int(p.id), as_of=datetime(2026, 2, 27, 0, 0, 0))
            r2 = build_program_rollup(db, program_id=int(p.id), as_of=datetime(2026, 2, 27, 0, 0, 0))
        finally:
            db.close()
    finally:
        eng.dispose()

    assert stable_json_dumps(r1) == stable_json_dumps(r2)
    posture = r1.get("program_posture") if isinstance(r1.get("program_posture"), dict) else {}
    assert isinstance(posture.get("rule_id"), str)
    assert isinstance(posture.get("cited_snapshot_ids"), list)
    assert isinstance(posture.get("cited_templates"), list)
    assert isinstance(posture.get("cited_decisions"), list)
    keys: set[str] = set()
    _collect_keys(posture, keys)
    banned = {"score", "weight", "points", "ranking_score", "numeric_total"}
    assert not (keys & banned)

