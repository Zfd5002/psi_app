from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services.portfolio import (
    build_portfolio_summary,
    build_program_portfolio_summary,
    build_portfolio_program_summaries,
    build_molecule_leaderboard,
    build_evidence_gap_report,
    build_portfolio_timeline,
    build_portfolio_export_rows,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_portfolio_summary_counts() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p1 = Program(name="P1", created_at=now, updated_at=now)
            p2 = Program(name="P2", created_at=now, updated_at=now)
            db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)
            m1 = Molecule(program_id=int(p1.id), primary_id="M1", title="m1", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p1.id), primary_id="M2", title="m2", created_at=now, updated_at=now)
            m3 = Molecule(program_id=int(p2.id), primary_id="M3", title="m3", created_at=now, updated_at=now)
            db.add_all([m1, m2, m3]); db.commit(); db.refresh(m1); db.refresh(m2); db.refresh(m3)
            db.add_all(
                [
                    DecisionSnapshot(
                        program_id=int(p1.id), molecule_id=int(m1.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
                        inputs_json="{}", outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}), evidence_ids_json="[]", is_superseded=0, created_at=now,
                    ),
                    DecisionSnapshot(
                        program_id=int(p1.id), molecule_id=int(m2.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
                        inputs_json="{}", outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"G": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}}, "blockers": []}), evidence_ids_json="[]", is_superseded=0, created_at=now,
                    ),
                ]
            )
            today = date.today()
            db.add_all(
                [
                    ExperimentTask(program_id=int(p1.id), molecule_id=int(m1.id), status="blocked", due_date=(today - timedelta(days=1)).isoformat(), created_at=now, updated_at=now),
                    ExperimentTask(program_id=int(p1.id), molecule_id=int(m2.id), status="in_progress", due_date=(today + timedelta(days=2)).isoformat(), created_at=now, updated_at=now),
                    ExperimentTask(program_id=int(p2.id), molecule_id=int(m3.id), status="done", due_date=(today - timedelta(days=2)).isoformat(), created_at=now, updated_at=now),
                ]
            )
            db.commit()

            out = build_portfolio_summary(db)
            assert out["program_count"] == 2
            assert out["molecule_count"] == 3
            assert out["task_count"] == 3
            assert out["blocked_tasks"] == 1
            assert out["overdue_tasks"] == 1
            assert out["tasks_blocked"] == 1
            assert out["tasks_overdue"] == 1
            assert out["tasks_in_progress"] == 1
            assert out["tasks_unassigned"] == 2
            assert out["ready_molecules"] == 1
            assert out["missing_data_molecules"] == 1
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_program_portfolio_summary_counts() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="PX", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m1 = Molecule(program_id=int(p.id), primary_id="A", title="A", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p.id), primary_id="B", title="B", created_at=now, updated_at=now)
            m3 = Molecule(program_id=int(p.id), primary_id="C", title="C", created_at=now, updated_at=now)
            db.add_all([m1, m2, m3]); db.commit(); db.refresh(m1); db.refresh(m2); db.refresh(m3)
            db.add_all(
                [
                    DecisionSnapshot(
                        program_id=int(p.id), molecule_id=int(m1.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
                        inputs_json="{}", outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}), evidence_ids_json="[]", is_superseded=0, created_at=now,
                    ),
                    DecisionSnapshot(
                        program_id=int(p.id), molecule_id=int(m2.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
                        inputs_json="{}", outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"G": {"status": "fail", "missing": [], "failed_metrics": ["ec50"]}}, "blockers": []}), evidence_ids_json="[]", is_superseded=0, created_at=now,
                    ),
                    DecisionSnapshot(
                        program_id=int(p.id), molecule_id=int(m3.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
                        inputs_json="{}", outputs_json=json.dumps({"decision_state": "not_ready", "gate_outcomes": {"G": {"status": "fail", "missing": ["kd_nM"], "failed_metrics": []}}, "blockers": []}), evidence_ids_json="[]", is_superseded=0, created_at=now,
                    ),
                ]
            )
            today = date.today()
            db.add_all(
                [
                    ExperimentTask(program_id=int(p.id), molecule_id=int(m1.id), status="in_progress", due_date=(today + timedelta(days=1)).isoformat(), created_at=now, updated_at=now),
                    ExperimentTask(program_id=int(p.id), molecule_id=int(m2.id), status="blocked", due_date=(today - timedelta(days=1)).isoformat(), created_at=now, updated_at=now),
                    ExperimentTask(program_id=int(p.id), molecule_id=int(m3.id), status="done", due_date=(today - timedelta(days=2)).isoformat(), created_at=now, updated_at=now),
                ]
            )
            db.commit()

            out = build_program_portfolio_summary(db, program_id=int(p.id))
            assert out["molecules_ready"] == 1
            assert out["molecules_failed"] == 1
            assert out["molecules_missing_data"] == 1
            assert out["open_tasks"] == 2
            assert out["overdue_tasks"] == 1
            assert out["blocked_tasks"] == 1
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_program_ordering_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p1 = Program(name="P1", created_at=now, updated_at=now)
            p2 = Program(name="P2", created_at=now, updated_at=now)
            p3 = Program(name="P3", created_at=now, updated_at=now)
            db.add_all([p1, p2, p3]); db.commit(); db.refresh(p1); db.refresh(p2); db.refresh(p3)
            m1 = Molecule(program_id=int(p1.id), primary_id="P1-M1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p2.id), primary_id="P2-M1", title="", created_at=now, updated_at=now)
            m3 = Molecule(program_id=int(p3.id), primary_id="P3-M1", title="", created_at=now, updated_at=now)
            m4 = Molecule(program_id=int(p3.id), primary_id="P3-M2", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2, m3, m4]); db.commit(); db.refresh(m1); db.refresh(m2); db.refresh(m3); db.refresh(m4)
            db.add_all(
                [
                    DecisionSnapshot(program_id=int(p1.id), molecule_id=int(m1.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(p2.id), molecule_id=int(m2.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"not_ready","gate_outcomes":{"G":{"status":"fail","missing":["kd_nM"],"failed_metrics":[]}},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(p3.id), molecule_id=int(m3.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(p3.id), molecule_id=int(m4.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                ]
            )
            db.add_all(
                [
                    ExperimentTask(program_id=int(p1.id), molecule_id=int(m1.id), status="in_progress", created_at=now, updated_at=now),
                    ExperimentTask(program_id=int(p2.id), molecule_id=int(m2.id), status="in_progress", created_at=now, updated_at=now),
                ]
            )
            db.commit()

            rows = build_portfolio_program_summaries(db)
            # p3: highest readiness, p1 next, p2 last.
            assert [int(r["program_id"]) for r in rows] == [int(p3.id), int(p1.id), int(p2.id)]
            assert str(rows[0]["heat_label"]) in {"progressing", "blocked", "evidence_gaps"}
        finally:
            db.close()
    finally:
        eng.dispose()


def test_readiness_score_penalizes_task_backlog() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            pa = Program(name="PA", created_at=now, updated_at=now)
            pb = Program(name="PB", created_at=now, updated_at=now)
            db.add_all([pa, pb]); db.commit(); db.refresh(pa); db.refresh(pb)
            ma = Molecule(program_id=int(pa.id), primary_id="PA-M1", title="", created_at=now, updated_at=now)
            mb = Molecule(program_id=int(pb.id), primary_id="PB-M1", title="", created_at=now, updated_at=now)
            db.add_all([ma, mb]); db.commit(); db.refresh(ma); db.refresh(mb)
            db.add_all(
                [
                    DecisionSnapshot(program_id=int(pa.id), molecule_id=int(ma.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(pb.id), molecule_id=int(mb.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                ]
            )
            # PB carries higher execution burden.
            db.add_all(
                [
                    ExperimentTask(program_id=int(pb.id), molecule_id=int(mb.id), status="in_progress", created_at=now, updated_at=now),
                    ExperimentTask(program_id=int(pb.id), molecule_id=int(mb.id), status="blocked", created_at=now, updated_at=now),
                ]
            )
            db.commit()

            rows = build_portfolio_program_summaries(db)
            by_pid = {int(r["program_id"]): r for r in rows}
            assert float(by_pid[int(pa.id)]["readiness_score"]) > float(by_pid[int(pb.id)]["readiness_score"])
        finally:
            db.close()
    finally:
        eng.dispose()


def test_molecule_leaderboard_prefers_ready_with_evidence_and_low_missing() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="PL", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m1 = Molecule(program_id=int(p.id), primary_id="M-L1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p.id), primary_id="M-L2", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2]); db.commit(); db.refresh(m1); db.refresh(m2)
            db.add_all(
                [
                    DecisionSnapshot(program_id=int(p.id), molecule_id=int(m1.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(p.id), molecule_id=int(m2.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"not_ready","gate_outcomes":{"G":{"status":"fail","missing":["kd_nM"],"failed_metrics":[]}},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                ]
            )
            # add evidence rows for m1
            db.add_all(
                [
                    DataRecord(program_id=int(p.id), molecule_id=int(m1.id), batch_id=None, domain="Biological", data_type="Binding", method="BLI", title="r1", created_at=now, updated_at=now),
                    DataRecord(program_id=int(p.id), molecule_id=int(m1.id), batch_id=None, domain="Biological", data_type="Binding", method="BLI", title="r2", created_at=now, updated_at=now),
                ]
            )
            db.commit()
            rows = build_molecule_leaderboard(db, limit=10)
            assert len(rows) >= 2
            assert int(rows[0]["molecule_id"]) == int(m1.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_evidence_gap_report_counts_missing_metrics() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="PG", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m1 = Molecule(program_id=int(p.id), primary_id="G1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p.id), primary_id="G2", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2]); db.commit(); db.refresh(m1); db.refresh(m2)
            db.add_all(
                [
                    DecisionSnapshot(program_id=int(p.id), molecule_id=int(m1.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"not_ready","gate_outcomes":{"G":{"status":"fail","missing":["kd_nM","sec_monomer_pct"],"failed_metrics":[]}},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(p.id), molecule_id=int(m2.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"not_ready","gate_outcomes":{"G":{"status":"fail","missing":["kd_nM"],"failed_metrics":[]}},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                ]
            )
            db.commit()
            rows = build_evidence_gap_report(db, limit=10)
            assert rows[0]["metric_key"] == "kd_nM"
            assert int(rows[0]["missing_molecule_count"]) == 2
        finally:
            db.close()
    finally:
        eng.dispose()


def test_program_bottleneck_detection_flags_concentrated_missing_metric() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="PBOT", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m1 = Molecule(program_id=int(p.id), primary_id="B1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p.id), primary_id="B2", title="", created_at=now, updated_at=now)
            m3 = Molecule(program_id=int(p.id), primary_id="B3", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2, m3]); db.commit(); db.refresh(m1); db.refresh(m2); db.refresh(m3)
            for m in (m1, m2, m3):
                miss = ["kd_nM"] if m in (m1, m2) else ["sec_monomer_pct"]
                db.add(
                    DecisionSnapshot(
                        program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1",
                        inputs_json="{}", outputs_json=json.dumps({"decision_state":"not_ready","gate_outcomes":{"G":{"status":"fail","missing":miss,"failed_metrics":[]}},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now,
                    )
                )
            db.commit()
            rows = build_portfolio_program_summaries(db)
            r = [x for x in rows if int(x["program_id"]) == int(p.id)][0]
            assert any(str(b).startswith("missing_metric_concentration:") for b in (r.get("bottleneck_badges") or []))
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_timeline_aggregates_weekly_activity() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7, 12, 0, 0)
            p = Program(name="PTL", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="T1", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            db.add_all(
                [
                    ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="done", created_at=now - timedelta(days=1), updated_at=now),
                    ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now - timedelta(days=8), updated_at=now - timedelta(days=8)),
                    DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="Biological", data_type="Binding", method="BLI", title="timeline-row", created_at=now - timedelta(days=2), updated_at=now - timedelta(days=2)),
                ]
            )
            db.commit()
            rows = build_portfolio_timeline(db, weeks=3)
            assert len(rows) == 3
            total_created = sum(int(r["tasks_created"]) for r in rows)
            total_done = sum(int(r["tasks_completed"]) for r in rows)
            total_evidence = sum(int(r["evidence_created"]) for r in rows)
            assert total_created == 2
            assert total_done == 1
            assert total_evidence == 1
        finally:
            db.close()
    finally:
        eng.dispose()


def test_portfolio_export_rows_follow_program_ordering() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p1 = Program(name="PX-1", created_at=now, updated_at=now)
            p2 = Program(name="PX-2", created_at=now, updated_at=now)
            db.add_all([p1, p2]); db.commit(); db.refresh(p1); db.refresh(p2)
            m1 = Molecule(program_id=int(p1.id), primary_id="M1", title="", created_at=now, updated_at=now)
            m2 = Molecule(program_id=int(p2.id), primary_id="M2", title="", created_at=now, updated_at=now)
            db.add_all([m1, m2]); db.commit(); db.refresh(m1); db.refresh(m2)
            db.add_all(
                [
                    DecisionSnapshot(program_id=int(p1.id), molecule_id=int(m1.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"ready","gate_outcomes":{},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                    DecisionSnapshot(program_id=int(p2.id), molecule_id=int(m2.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json=json.dumps({"decision_state":"not_ready","gate_outcomes":{"G":{"status":"fail","missing":["kd_nM"],"failed_metrics":[]}},"blockers":[]}), evidence_ids_json="[]", is_superseded=0, created_at=now),
                ]
            )
            db.commit()
            rows = build_portfolio_export_rows(db)
            assert len(rows) == 2
            assert rows[0]["program_name"] == "PX-1"
            assert rows[1]["program_name"] == "PX-2"
            assert "program_status" in rows[0]
        finally:
            db.close()
    finally:
        eng.dispose()
