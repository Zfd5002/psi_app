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
    )
    assert "Lineage" in html
    assert "Parent molecule" in html
    assert "Child molecules" in html
    assert "M-9" in html
    assert "M-11" in html
