from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import plans as plans_svc
from psi.services import programs as program_svc
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    env.filters["humanize_key"] = humanize_key
    return env


def test_program_detail_includes_program_narrative_context() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-pn", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-pn", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            plan = plans_svc.create_plan(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), claim_id=None, title="Plan", plan_type="readiness_advancement", status="recommended")
            plans_svc.add_plan_step(db, plan_id=int(plan.id), metric_key="kd_nM", suggested_assay="SPR", step_kind="experiment")
            old_sql = program_svc.PROGRAM_EVIDENCE_ROWS_SQL
            program_svc.PROGRAM_EVIDENCE_ROWS_SQL = """
            SELECT dr.molecule_id AS molecule_id, dm.name AS metric_key
            FROM data_records dr
            JOIN data_measurements dm ON dm.data_record_id = dr.id
            WHERE dr.program_id = :pid AND dr.molecule_id IS NOT NULL
            ORDER BY dr.molecule_id ASC, dm.name ASC, dm.id ASC
            """
            ctx = program_svc.get_program_detail(db, int(p.id))
            program_svc.PROGRAM_EVIDENCE_ROWS_SQL = old_sql
            assert "program_narrative" in ctx
            assert "scientific_thesis" in ctx["program_narrative"]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_program_detail_template_renders_narrative_panel() -> None:
    tpl = _env().get_template("programs/detail.html")
    html = tpl.render(
        request=SimpleNamespace(query_params={}),
        program=SimpleNamespace(id=1, name="P", description=""),
        molecules=[],
        recent_batches=[],
        recent_data=[],
        recent_evidence=[],
        recent_decisions=[],
        audits=[],
        review_queue_by_molecule=[],
        open_experiment_tasks_preview=[],
        candidate_set={},
        program_molecule_status_board=[],
        program_evidence_summary={},
        program_evidence_matrix=[],
        program_suggested_experiments=[],
        program_claim_summary={},
        program_claims_preview=[],
        program_plan_summary={},
        program_plans_preview=[],
        program_dashboard={
            "molecule_count": 0,
            "active_contender_count": 0,
            "posture_label": "UNKNOWN",
            "pending_entry_count": 0,
            "role_counts": {"lead": 0, "backup": 0, "active": 0, "watchlist": 0, "deprioritized": 0, "archived": 0},
            "progress_percent": 0.0,
            "confidence_percent": 0.0,
            "progress_label": "unknown",
            "confidence_label": "low",
            "progress_basis": "",
            "confidence_basis": "",
        },
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
        program_memberships_v3=[],
        all_molecules_for_membership=[],
        program_molecule_role_options=[],
        program_narrative={
            "scientific_thesis": "Program thesis text",
            "current_state_summary": "Current state text",
            "strongest_support": ["Support A"],
            "major_uncertainties": ["Uncertainty A"],
            "next_milestone": "Next milestone text",
        },
    )
    assert "Program Narrative" in html
    assert "Program thesis text" in html
    assert "/programs/1/narrative" in html
