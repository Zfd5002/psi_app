from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, MoleculeDerivation, Program
from psi.services import molecules as molecule_svc
from psi.web.ui_labels import humanize_path_token, humanize_state


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
    return env


def test_molecule_detail_context_includes_lineage_parent_and_children() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Lineage-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)

            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="LINEAGE-PARENT",
                title="Lineage Parent",
                components={"HC1": "AAAA", "LC1": "BBBB"},
            )
            child_a = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="LINEAGE-CHILD-A",
                title="Child A",
                components={"HC1": "AAAC", "LC1": "BBBB"},
            )
            child_b = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="LINEAGE-CHILD-B",
                title="Child B",
                components={"HC1": "AAAD", "LC1": "BBBB"},
            )

            db.add(
                MoleculeDerivation(
                    parent_molecule_id=int(parent.id),
                    child_molecule_id=int(child_a.id),
                    derivation_type="point_mutation",
                    summary="S32A",
                    edit_payload_json="{}",
                    created_at=datetime(2026, 3, 7, 10, 0, 0),
                )
            )
            db.add(
                MoleculeDerivation(
                    parent_molecule_id=int(parent.id),
                    child_molecule_id=int(child_b.id),
                    derivation_type="clone",
                    summary="builder clone",
                    edit_payload_json="{}",
                    created_at=datetime(2026, 3, 7, 11, 0, 0),
                )
            )
            db.commit()

            child_ctx = molecule_svc.get_molecule_detail(db, int(child_a.id))
            assert child_ctx["lineage_parent"] is not None
            assert child_ctx["lineage_parent"]["primary_id"] == "LINEAGE-PARENT"
            assert child_ctx["lineage_parent"]["derivation_type"] == "point_mutation"
            assert "trajectory_candidates" in child_ctx
            assert isinstance(child_ctx["trajectory_candidates"], list)
            assert "trajectory_tree" in child_ctx
            assert isinstance(child_ctx["trajectory_tree"], dict)

            parent_ctx = molecule_svc.get_molecule_detail(db, int(parent.id))
            children = parent_ctx["lineage_children"]
            assert [c["primary_id"] for c in children] == ["LINEAGE-CHILD-B", "LINEAGE-CHILD-A"]
            assert children[0]["derivation_type"] == "clone"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_molecule_detail_template_renders_lineage_panel() -> None:
    tpl = _env().get_template("molecules/detail.html")
    html = tpl.render(
        request=SimpleNamespace(query_params={}),
        tab="overview",
        molecule=SimpleNamespace(id=10, primary_id="M-10", title="Mol 10", description_user="", description="", description_auto=""),
        molecule_header_model={},
        lineage_parent={
            "molecule_id": 9,
            "primary_id": "M-9",
            "title": "Parent Mol",
            "derivation_type": "point_mutation",
            "summary": "S32A",
        },
        lineage_children=[
            {
                "molecule_id": 11,
                "primary_id": "M-11",
                "title": "Child Mol",
                "derivation_type": "clone",
                "summary": "builder clone",
            }
        ],
        exp_batch_panels=[],
        data_records=[],
        evidence=[],
        file_links=[],
        files_by_id={},
        audits=[],
        components=[],
        domain_instances=[],
        latest_values_parsed=[],
        immuno_values_parsed=[],
        latest_run_events=[],
        di_history=[],
        exp_batches=[],
        exp_qc_mode="all",
        heavy_gate_overall=SimpleNamespace(ok=True),
        heavy_gate_domains=SimpleNamespace(ok=True),
        heavy_gate_numbering=SimpleNamespace(ok=True),
        viewer_v2_components=[],
        numbering_maps={},
        numbering_payload={},
        pdl1_allowed_mismatches=0,
        sequence_editor_annotations=[],
        molecule_insight_bundle={
            "molecule_status": "blocked",
            "blocking_issues": [{"gate_key": "sec_gate", "status": "fail"}],
            "missing_evidence": [{"metric_key": "kd_nM"}],
            "recommended_experiments": [{"suggested_assay": "Add measurement for kd_nM"}],
            "strongest_blocking_evidence": [
                {
                    "metric_key": "monomer_pct",
                    "observed_value": 72.0,
                    "required_threshold": "Monomer >= 85 %",
                    "batch": "B-1",
                }
            ],
        },
        molecule_insight_source={"snapshot_id": 12, "decision_key": "advance_to_in_vivo", "created_at": "2026-03-07"},
        molecule_insight_governance={
            "policy_name": "readiness_policy",
            "policy_version": "v0.2",
            "policy_semantics_hash": "abc123",
            "snapshot_content_hash": "def456",
            "gate_outcomes": [{"gate_key": "sec_gate", "status": "fail"}],
        },
        molecule_trends={
            "metric_keys": ["monomer_pct"],
            "series": {"monomer_pct": [{"value": 82.0}, {"value": 85.0}]},
        },
        molecule_trend_insights=[{"metric_key": "monomer_pct", "signal": "improving"}],
        open_experiment_tasks=[
            {
                "id": 41,
                "status": "planned",
                "urgency": "high",
                "owner_text": "Dr. A",
                "due_date": "2026-03-12",
                "metric_key": "kd_nM",
                "suggested_assay": "SPR",
            }
        ],
        trajectory_candidates=[
            {
                "metric_key": "kd_nM",
                "suggested_assay": "BLI",
                "expected_readiness_gain": 1,
                "gate_impact": 1,
                "confidence_level": "high",
                "confidence_score": 0.82,
            }
        ],
        trajectory_tree={
            "nodes": [
                {"node_id": "root", "parent_id": None},
                {"node_id": "n1_0", "parent_id": "root", "metric_key": "kd_nM", "suggested_assay": "BLI", "readiness_after": "ready"},
            ]
        },
    )
    assert "Lineage" in html
    assert "Parent molecule" in html
    assert "Child molecules" in html
    assert "M-9" in html
    assert "M-11" in html
    assert "sequence_editor_tooltip" in html
    assert "/static/sequence_editor.js" in html
    assert "What This Molecule Needs Next" in html
    assert "Operational Tasks" in html
    assert "#41" in html
    assert "Start" in html
    assert "Add measurement for kd_nM" in html
    assert "Blocking evidence detail" in html
    assert "Monomer &gt;= 85 %" in html or "Monomer >= 85 %" in html
    assert "Insight Governance Detail" in html
    assert "Gate outcomes" in html
    assert "Trend Signals" in html
    assert "trend-sparkline" in html
    assert "monomer_pct: improving" in html
    assert "Scientific Trajectory" in html
    assert "Expected readiness gain" in html
    assert "BLI" in html
    assert "Trajectory Graph" in html
    assert "Current state" in html
    assert "root → n1_0" in html
