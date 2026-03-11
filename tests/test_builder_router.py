from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, ExperimentTask, Molecule, Program
from psi.web.routers import builder as builder_router
from psi.web.ui_labels import humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_state"] = humanize_state
    return env


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_builder_routes_exist() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set())))) for r in builder_router.router.routes}
    assert ("/builder", ("GET",)) in route_keys
    assert ("/builder/clone", ("GET",)) in route_keys
    assert ("/builder/clone/draft", ("POST",)) in route_keys
    assert ("/builder/clone/create", ("POST",)) in route_keys
    assert ("/builder/point-mutation", ("GET",)) in route_keys
    assert ("/builder/point-mutation/draft", ("POST",)) in route_keys
    assert ("/builder/point-mutation/create", ("POST",)) in route_keys
    assert ("/builder/cdr-builder", ("GET",)) in route_keys
    assert ("/builder/cdr-builder/draft", ("POST",)) in route_keys
    assert ("/builder/search_molecules", ("GET",)) in route_keys
    assert ("/builder/parent_context", ("GET",)) in route_keys
    assert ("/builder/exploration-task", ("POST",)) in route_keys


def test_builder_parent_context_returns_suggested_new_primary_id() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P-builder-context")
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = Molecule(program_id=int(p.id), primary_id="TUT1-A001", title="Parent")
            sibling = Molecule(program_id=int(p.id), primary_id="TUT1-A002", title="Sibling")
            db.add_all([parent, sibling])
            db.commit()
            db.refresh(parent)
            resp = builder_router.builder_parent_context(parent_molecule_id=int(parent.id), db=db)
            assert resp.status_code == 200
            payload = json.loads(resp.body.decode("utf-8"))
            assert int(payload["parent_molecule_id"]) == int(parent.id)
            assert int(payload["program_id"]) == int(p.id)
            assert payload["series_prefix"] == "TUT1-A"
            assert payload["suggested_new_primary_id"] == "TUT1-A003"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_create_builder_exploration_task_route_creates_operational_task() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P-builder-task")
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-B1", title="builder-mol")
            db.add(m)
            db.commit()
            db.refresh(m)

            resp = builder_router.create_builder_exploration_task(
                parent_molecule_id=int(m.id),
                task_title="create_variant",
                notes="explore substitutions",
                action_target="point-mutation",
                redirect_to="",
                db=db,
            )
            assert resp.status_code == 303
            assert "/builder/point-mutation" in str(resp.headers.get("location") or "")
            rows = db.query(ExperimentTask).order_by(ExperimentTask.id.asc()).all()
            assert len(rows) == 1
            assert str(rows[0].source_kind or "") == "builder_exploration"
            assert str(rows[0].suggested_assay or "") == "builder:point-mutation"
            assert int(rows[0].program_id) == int(p.id)
            assert int(rows[0].molecule_id) == int(m.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_builder_index_template_renders_standalone_builder_surface() -> None:
    tpl = _env().get_template("builder/index.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[
            SimpleNamespace(id=11, primary_id="M-11", title="Mol11"),
            SimpleNamespace(id=12, primary_id="M-12", title="Mol12"),
        ],
    )
    assert "Molecule Builder" in html
    assert "Open clone flow" in html
    assert "Open point mutation flow" in html
    assert "/builder/clone" in html
    assert "/builder/point-mutation" in html
    assert "/builder/cdr-builder" in html
    assert "/molecules/11" in html


def test_builder_clone_template_has_preview_first_actions() -> None:
    tpl = _env().get_template("builder/clone.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=None,
        form_data={},
        error="",
    )
    assert "Build draft" in html
    assert 'action="/builder/clone/draft"' in html
    assert 'id="builder_parent_search"' in html


def test_builder_point_mutation_template_has_preview_first_actions() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=None,
        form_data={},
        error="",
    )
    assert "Build draft" in html
    assert 'action="/builder/point-mutation/draft"' in html
    assert 'id="builder_parent_search"' in html


def test_builder_point_mutation_template_renders_before_after_preview() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=SimpleNamespace(
            errors=[],
            warnings=[],
            assumptions=[],
            parent_primary_id="M-11",
            derivation_type="point_mutation",
            preview_rows=[
                {
                    "component": "HC1",
                    "before": "MSGN",
                    "after": "MAGQ",
                    "mutations": "S2A N4Q",
                    "diff_rows": [
                        {
                            "start": 1,
                            "end": 4,
                            "original": [
                                {"aa": "M", "changed": False},
                                {"aa": "S", "changed": True},
                                {"aa": "G", "changed": False},
                                {"aa": "N", "changed": True},
                            ],
                            "edited": [
                                {"aa": "M", "changed": False},
                                {"aa": "A", "changed": True},
                                {"aa": "G", "changed": False},
                                {"aa": "Q", "changed": True},
                            ],
                        }
                    ],
                }
            ],
            changed_residues=[{"component": "HC1", "position": "2", "from": "S", "to": "A"}],
            components={"HC1": "MAGQ", "LC1": "BBBB"},
            parent_molecule_id=11,
            new_primary_id="M-11-mut",
            new_title="Mutant",
        ),
        form_data={"component": "HC1", "mutations": "S2A N4Q", "rationale": ""},
        error="",
    )
    assert "S2A N4Q" in html
    assert "Changed residues" in html
    assert "Sequence diff view" in html
    assert "builder-draft-diff" in html
    assert "seq-diff-block" in html
    assert "seq-diff-aa" in html
    assert "seq-diff-aa is-changed" in html
    assert html.count("seq-diff-block") == 1
    assert "Diff summary" not in html
    assert "<th>Before</th>" not in html
    assert "<th>After</th>" not in html
    assert 'action="/builder/point-mutation/create"' in html


def test_builder_point_mutation_template_hides_create_when_draft_invalid() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=SimpleNamespace(
            errors=["WT mismatch at position 2"],
            warnings=[],
            assumptions=[],
            parent_primary_id="M-11",
            derivation_type="point_mutation",
            preview_rows=[],
            changed_residues=[],
            components={"HC1": "MSGN", "LC1": "BBBB"},
            parent_molecule_id=11,
            new_primary_id="M-11-mut",
            new_title="Mutant",
        ),
        form_data={"component": "HC1", "mutations": "T2A", "rationale": ""},
        error="",
    )
    assert "Draft has validation errors" in html
    assert 'action="/builder/point-mutation/create"' not in html


def test_builder_point_mutation_template_shows_sequence_editor_handoff_context() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=None,
        form_data={
            "queue_origin": "sequence_editor",
            "source_primary_id": "M-11",
            "queued_component": "HC1",
            "queued_mutation_count": 2,
            "queued_mutation_tokens": "S2A N4Q",
        },
        error="",
    )
    assert "Sequence editor handoff" in html
    assert "Source molecule: M-11" in html
    assert "Component: HC1" in html
    assert "Mutation count: 2" in html
    assert "Tokens: S2A N4Q" in html


def test_builder_point_mutation_template_shows_mutation_normalization_notes() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=None,
        form_data={"mutation_validation_errors": ["WT mismatch at 2: expected T, found S"]},
        error="",
    )
    assert "Mutation normalization notes" in html
    assert "WT mismatch at 2: expected T, found S" in html
