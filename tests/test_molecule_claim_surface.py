from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import claims as claims_svc
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


def test_molecule_detail_includes_claim_rows() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-mc", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-mc", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Affinity claim",
                claim_type="affinity",
                statement="Molecule has high affinity.",
                status="emerging",
            )
            ctx = molecule_svc.get_molecule_detail(db, int(m.id))
            assert "molecule_claims" in ctx
            assert len(ctx["molecule_claims"]) >= 1
            assert str(ctx["molecule_claims"][0]["title"]) == "Affinity claim"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_molecule_claim_panel_renders() -> None:
    tpl = _env().get_template("molecules/detail.html")
    html = tpl.render(
        request=SimpleNamespace(query_params={}),
        tab="overview",
        molecule=SimpleNamespace(id=10, primary_id="M-10", title="", description_user="", description="", description_auto=""),
        molecule_header_model={},
        lineage_parent=None,
        lineage_children=[],
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
        molecule_insight_bundle={},
        molecule_insight_source={},
        molecule_insight_governance={},
        molecule_trends={},
        molecule_trend_insights=[],
        open_experiment_tasks=[],
        trajectory_candidates=[],
        trajectory_tree={"nodes": []},
        molecule_claims=[
            {
                "claim_id": 11,
                "title": "Affinity claim",
                "claim_type": "affinity",
                "status": "emerging",
                "confidence_level": "medium",
                "supporting_count": 2,
                "contradicting_count": 0,
                "maturity_summary": "emerging",
                "next_task_label": "BLI",
            }
        ],
    )
    assert "Scientific Claims" in html
    assert "Affinity claim" in html
    assert "/claims/11" in html
