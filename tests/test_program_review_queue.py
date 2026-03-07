from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, Molecule, Program
from psi.services.data_records import apply_bulk_qc_action_for_record, create_data_record
from psi.services.programs import PROGRAM_EVIDENCE_ROWS_SQL, build_program_review_queue
from psi.web.routers import programs as programs_router
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


class _Req:
    query_params = {}

    @staticmethod
    def url_for(name: str, **path_params) -> str:
        rid = int(path_params.get("record_id", 0))
        pid = int(path_params.get("program_id", 0))
        if name == "approve_record_qc":
            return f"/data/{rid}/qc/approve"
        if name == "reject_record_qc":
            return f"/data/{rid}/qc/reject"
        if name == "program_review_approve_all":
            return f"/programs/{pid}/review/approve-all"
        if name == "program_review_reject_all":
            return f"/programs/{pid}/review/reject-all"
        return "/"


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    with eng.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(data_measurements)").mappings().all()
        col_names = {str(r.get('name') or '') for r in cols}
        if "metric_key" not in col_names:
            conn.exec_driver_sql("ALTER TABLE data_measurements ADD COLUMN metric_key TEXT")
        if "name" in col_names:
            conn.exec_driver_sql("UPDATE data_measurements SET metric_key = COALESCE(metric_key, name)")
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _sync_metric_key(db) -> None:
    db.execute(text("UPDATE data_measurements SET metric_key = COALESCE(metric_key, name)"))
    db.commit()


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_program_review_queue_deterministic_grouping_and_pending_filter() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P1", description="", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p); db.commit(); db.refresh(p)
            ma = Molecule(program_id=int(p.id), primary_id="A-1", title="A", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            mb = Molecule(program_id=int(p.id), primary_id="B-1", title="B", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add_all([ma, mb]); db.commit(); db.refresh(ma); db.refresh(mb)
            ba = Batch(molecule_id=int(ma.id), batch_id="BA", title="BA", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            bb = Batch(molecule_id=int(mb.id), batch_id="BB", title="BB", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add_all([ba, bb]); db.commit(); db.refresh(ba); db.refresh(bb)
            rec_a = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(ma.id),
                batch_id=int(ba.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="A run",
                results_json={"ec50": 1.2},
            )
            rec_b = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(mb.id),
                batch_id=int(bb.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="B run",
                results_json={"kd": 2.3},
            )
            _sync_metric_key(db)
            # Fully approve B entry so only A remains pending.
            apply_bulk_qc_action_for_record(db, record_id=int(rec_b.id), action="approve", actor="scientist")
            queue = build_program_review_queue(db, program_id=int(p.id))
            assert len(queue) == 1
            assert queue[0]["molecule_primary_id"] == "A-1"
            assert len(queue[0]["records"]) == 1
            assert queue[0]["records"][0]["record_id"] == int(rec_a.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_program_detail_template_renders_review_queue_actions_and_order() -> None:
    tpl = _env().get_template("programs/detail.html")
    queue = [
        {"molecule_id": 2, "molecule_primary_id": "A-1", "molecule_title": "A", "records": [{"record_id": 11, "created_at": "2026-03-03T00:00:00", "batch_id": 5, "assay_key": "IN_VIVO_EFFICACY/NOD", "preview_snippet": "EC50"}]},
        {"molecule_id": 3, "molecule_primary_id": "B-1", "molecule_title": "B", "records": [{"record_id": 12, "created_at": "2026-03-03T00:00:00", "batch_id": 6, "assay_key": "PK_PD/NONCOMP", "preview_snippet": "KD"}]},
    ]
    html = tpl.render(
        request=_Req(),
        program=SimpleNamespace(id=1, name="P1", description=""),
        program_memberships_v3=[
            {
                "membership_id": 1,
                "program_id": 1,
                "molecule_id": 2,
                "sort_index": 0,
                "primary_id": "A-1",
                "title": "A",
                "owner_program_id": 1,
                "candidate_role": "lead",
                "candidate_role_rationale": "best profile",
            }
        ],
        program_molecule_role_options=["lead", "backup", "active", "watchlist", "deprioritized", "archived"],
        all_molecules_for_membership=[],
        molecules=[],
        recent_batches=[],
        recent_data=[],
        recent_evidence=[],
        recent_decisions=[],
        review_queue_by_molecule=queue,
        di_dashboard={
            "counts": {"READY": 0, "BLOCKED": 0, "UNKNOWN": 0},
            "policy_version_filter": None,
            "policy_versions": [],
            "policy_ids": [],
            "top_blockers": [],
            "top_missing_metrics": [],
            "top_failing_gates": [],
            "metric_coverage": [],
            "qc_ignore_reasons": [],
            "qc_failed_metrics": [],
            "qc_unreviewed_metrics": [],
            "molecule_rollup": [],
            "molecule_rollup_filtered": [],
            "lineage": [],
            "lineage_verify_enabled": False,
        },
        program_dashboard={
            "molecule_count": 2,
            "active_contender_count": 2,
            "posture_label": "READY",
            "pending_entry_count": 2,
            "role_counts": {
                "lead": 1,
                "backup": 1,
                "active": 0,
                "watchlist": 0,
                "deprioritized": 0,
                "archived": 0,
            },
            "progress_percent": 100.0,
            "confidence_percent": 100.0,
            "progress_label": "advanced",
            "confidence_label": "high",
            "progress_basis": "derived_from_latest_molecule_readiness_states",
            "confidence_basis": "derived_from_non_blocked_fraction_of_known_states",
        },
        candidate_set={
            "lead": [{"molecule_id": 2, "primary_id": "A-1", "title": "A", "rationale": "best profile", "sort_index": 0}],
            "backup": [{"molecule_id": 3, "primary_id": "B-1", "title": "B", "rationale": "", "sort_index": 1}],
            "active": [],
            "watchlist": [],
            "deprioritized": [],
            "archived": [],
        },
        program_molecule_status_board=[
            {
                "molecule_id": 2,
                "primary_id": "A-1",
                "title": "A",
                "role": "lead",
                "readiness_state": "READY",
                "key_blocker": "g3_endotoxin",
                "latest_evidence_update": "2026-03-07T00:00:00",
            }
        ],
        program_evidence_summary=[
            {"group": "Binding", "molecule_coverage_count": 2, "metric_key_count": 2},
        ],
        program_evidence_matrix={
            "groups": ["Binding"],
            "rows": [
                {
                    "molecule_id": 2,
                    "primary_id": "A-1",
                    "title": "A",
                    "cells": [{"group": "Binding", "present": True}],
                }
            ],
        },
        program_suggested_experiments=[
            "Close missing evidence for KD in priority candidates (lead:A-1, backup:B-1).",
        ],
        audits=[],
    )
    assert "Review data entries" in html
    assert "/programs/1/review/approve-all" in html
    assert "/programs/1/review/reject-all" in html
    assert "/data/11/qc/approve" in html
    assert "/data/11/qc/reject" in html
    assert "/data/11/edit?return_to=/programs/1" in html
    assert "/programs/1/molecules/2/role" in html
    assert "best profile" in html
    assert "Program progress (UI-only)" in html
    assert "Program confidence (UI-only)" in html
    assert "derived_from_latest_molecule_readiness_states" in html
    assert "derived_from_non_blocked_fraction_of_known_states" in html
    assert "Candidate Set" in html
    assert "None assigned." in html
    assert "Molecule Status Board" in html
    assert "G3 Endotoxin" in html
    assert "Program Evidence Summary" in html
    assert "Binding" in html
    assert "Program Evidence Map" in html
    assert "✓" in html
    assert "Suggested Next Experiments" in html
    assert "Program Drill-down" in html
    assert "/reports/new?report_type=program_report&subject_ids=1" in html
    assert 'id="record-11"' in html
    assert "psi_program_review_scroll_y" in html
    assert "review-queue-action-form" in html
    assert 'id="toggle-governance-program"' in html
    assert 'id="program-governance-panel"' in html
    assert 'data-program-governance-panel="true"' in html
    assert 'aria-hidden="true"' in html
    assert "psi_program_detail_mode" in html
    assert html.find("A-1") < html.find("B-1")


def test_program_detail_template_hides_bulk_buttons_when_no_pending() -> None:
    tpl = _env().get_template("programs/detail.html")
    html = tpl.render(
        request=_Req(),
        program=SimpleNamespace(id=1, name="P1", description=""),
        program_memberships_v3=[],
        program_molecule_role_options=["lead", "backup", "active", "watchlist", "deprioritized", "archived"],
        all_molecules_for_membership=[],
        molecules=[],
        recent_batches=[],
        recent_data=[],
        recent_evidence=[],
        recent_decisions=[],
        review_queue_by_molecule=[],
        di_dashboard={
            "counts": {"READY": 0, "BLOCKED": 0, "UNKNOWN": 0},
            "policy_version_filter": None,
            "policy_versions": [],
            "policy_ids": [],
            "top_blockers": [],
            "top_missing_metrics": [],
            "top_failing_gates": [],
            "metric_coverage": [],
            "qc_ignore_reasons": [],
            "qc_failed_metrics": [],
            "qc_unreviewed_metrics": [],
            "molecule_rollup": [],
            "molecule_rollup_filtered": [],
            "lineage": [],
            "lineage_verify_enabled": False,
        },
        program_dashboard={},
        candidate_set={},
        program_molecule_status_board=[],
        program_evidence_summary=[],
        program_evidence_matrix={},
        program_suggested_experiments=[],
        audits=[],
    )
    assert "/programs/1/review/approve-all" not in html
    assert "/programs/1/review/reject-all" not in html


def test_program_detail_governance_panel_hidden_by_default() -> None:
    tpl = _env().get_template("programs/detail.html")
    html = tpl.render(
        request=_Req(),
        program=SimpleNamespace(id=1, name="P1", description=""),
        program_memberships_v3=[],
        program_molecule_role_options=["lead", "backup", "active", "watchlist", "deprioritized", "archived"],
        all_molecules_for_membership=[],
        molecules=[],
        recent_batches=[],
        recent_data=[],
        recent_evidence=[],
        recent_decisions=[],
        review_queue_by_molecule=[],
        di_dashboard={
            "counts": {"READY": 0, "BLOCKED": 0, "UNKNOWN": 0},
            "policy_version_filter": None,
            "policy_versions": [],
            "policy_ids": [],
            "top_blockers": [],
            "top_missing_metrics": [],
            "top_failing_gates": [],
            "metric_coverage": [],
            "qc_ignore_reasons": [],
            "qc_failed_metrics": [],
            "qc_unreviewed_metrics": [],
            "molecule_rollup": [],
            "molecule_rollup_filtered": [],
            "lineage": [],
            "lineage_verify_enabled": False,
        },
        program_dashboard={},
        candidate_set={},
        program_molecule_status_board=[],
        program_evidence_summary=[],
        program_evidence_matrix={},
        program_suggested_experiments=[],
        audits=[],
    )
    assert "Show governance details" in html
    assert 'id="program-governance-panel"' in html
    assert 'style="display:none;"' in html
    assert 'aria-hidden="true"' in html
    assert "DI portfolio status (latest snapshot per molecule)" in html


def test_program_review_bulk_routes_exist() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set())))) for r in programs_router.router.routes}
    assert ("/programs/{program_id}/review/approve-all", ("POST",)) in route_keys
    assert ("/programs/{program_id}/review/reject-all", ("POST",)) in route_keys
    assert ("/programs/{program_id}/molecules/{molecule_id}/role", ("POST",)) in route_keys


def test_program_evidence_query_uses_metric_key_only() -> None:
    sql = str(PROGRAM_EVIDENCE_ROWS_SQL)
    assert "dm.metric_key" in sql
    assert "dm.name" not in sql
    assert "COALESCE(dm.metric_key, dm.name)" not in sql


def test_program_review_approve_all_endpoint_processes_pending_queue() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 3)
            p = Program(name="P-bulk", description="", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-bulk", title="MB", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-bulk", title="BB", created_at=now, updated_at=now)
            db.add(b); db.commit(); db.refresh(b)
            create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Pending 1",
                results_json={"ec50": 3.4},
            )
            create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Pending 2",
                results_json={"kd": 5.6},
            )
            _sync_metric_key(db)
            before = build_program_review_queue(db, program_id=int(p.id))
            assert sum(len(g.get("records") or []) for g in before) == 2
            resp = programs_router.program_review_approve_all(program_id=int(p.id), actor="scientist", db=db)
            assert getattr(resp, "status_code", None) == 303
            assert getattr(resp, "headers", {}).get("location") == f"/programs/{int(p.id)}"
            after = build_program_review_queue(db, program_id=int(p.id))
            assert sum(len(g.get("records") or []) for g in after) == 0
        finally:
            db.close()
    finally:
        eng.dispose()
