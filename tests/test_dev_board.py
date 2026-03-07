from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.measurement_schema import measurement_cols
from psi.core.models import Base, DataRecord, DecisionSnapshot, Molecule, Program
from psi.services import dev_board
from psi.services.dev_board import build_development_board


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_development_board_groups_molecules_deterministically() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-board", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)

            m_ready = Molecule(program_id=int(p.id), primary_id="M-A", title="ready", created_at=now, updated_at=now)
            m_fail = Molecule(program_id=int(p.id), primary_id="M-B", title="fail", created_at=now, updated_at=now)
            m_missing = Molecule(program_id=int(p.id), primary_id="M-C", title="missing", created_at=now, updated_at=now)
            m_none = Molecule(program_id=int(p.id), primary_id="M-D", title="none", created_at=now, updated_at=now)
            db.add_all([m_ready, m_fail, m_missing, m_none])
            db.commit()
            db.refresh(m_ready)
            db.refresh(m_fail)
            db.refresh(m_missing)
            db.refresh(m_none)

            db.add_all(
                [
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=int(m_ready.id),
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v1",
                        inputs_json="{}",
                        outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}),
                        evidence_ids_json="[]",
                        is_superseded=0,
                        created_at=now,
                    ),
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=int(m_fail.id),
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v1",
                        inputs_json="{}",
                        outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"G1": {"status": "fail", "missing": [], "failed_metrics": ["ec50"]}}, "blockers": []}),
                        evidence_ids_json="[]",
                        is_superseded=0,
                        created_at=now,
                    ),
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=int(m_missing.id),
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v1",
                        inputs_json="{}",
                        outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"G1": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}}, "blockers": []}),
                        evidence_ids_json="[]",
                        is_superseded=0,
                        created_at=now,
                    ),
                ]
            )
            db.commit()

            rec1 = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m_ready.id),
                batch_id=None,
                domain="CMC",
                data_type="CMC_Analytics",
                method="SEC_HPLC",
                title="t1",
                run_date="2026-03-01",
                created_at=now,
                updated_at=now,
            )
            rec2 = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m_ready.id),
                batch_id=None,
                domain="CMC",
                data_type="CMC_Analytics",
                method="SEC_HPLC",
                title="t2",
                run_date="2026-03-02",
                created_at=now,
                updated_at=now,
            )
            db.add_all([rec1, rec2])
            db.commit()
            db.refresh(rec1)
            db.refresh(rec2)
            cols = measurement_cols(db)
            db.execute(
                text(
                    f"""
                    INSERT INTO data_measurements ({cols['record_fk']}, {cols['name']}, {cols['value_num']}, {cols['created_at']})
                    VALUES (:rid, :mk, :val, :ts)
                    """
                ),
                [
                    {"rid": int(rec1.id), "mk": "monomer_pct", "val": 80.0, "ts": "2026-03-01"},
                    {"rid": int(rec2.id), "mk": "monomer_pct", "val": 88.0, "ts": "2026-03-02"},
                ],
            )
            db.commit()

            board = build_development_board(db, program_id=int(p.id))
            groups = board["groups"]
            assert [x["primary_id"] for x in groups["ready"]] == ["M-A"]
            assert [x["primary_id"] for x in groups["failed"]] == ["M-B"]
            assert [x["primary_id"] for x in groups["missing_data"]] == ["M-C"]
            assert [x["primary_id"] for x in groups["not_evaluated"]] == ["M-D"]
            assert groups["ready"][0]["trend_signal"] == "improving"
            assert isinstance(groups["failed"][0]["warnings"], list)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_board_cache_and_invalidation(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-board-cache", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-A", title="a", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}),
                evidence_ids_json="[]",
                is_superseded=0,
                created_at=now,
            )
            db.add(snap)
            db.commit()
            db.refresh(snap)

            calls = {"n": 0}
            orig = dev_board.build_insight_bundle

            def _counted(*args, **kwargs):
                calls["n"] += 1
                return orig(*args, **kwargs)

            monkeypatch.setattr(dev_board, "build_insight_bundle", _counted)
            dev_board.invalidate_program_board_cache(program_id=int(p.id))
            _ = build_development_board(db, program_id=int(p.id), use_cache=True)
            _ = build_development_board(db, program_id=int(p.id), use_cache=True)
            assert calls["n"] == 1
            dev_board.invalidate_program_board_cache(program_id=int(p.id))
            _ = build_development_board(db, program_id=int(p.id), use_cache=True)
            assert calls["n"] == 2
        finally:
            db.close()
    finally:
        eng.dispose()
