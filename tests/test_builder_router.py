from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.routers import builder as builder_router
from psi.web.ui_labels import humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_state"] = humanize_state
    return env


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
            preview_rows=[{"component": "HC1", "before": "MSGN", "after": "MAGQ", "mutations": "S2A N4Q"}],
            changed_residues=[{"component": "HC1", "position": "2", "from": "S", "to": "A"}],
            components={"HC1": "MAGQ", "LC1": "BBBB"},
            parent_molecule_id=11,
            new_primary_id="M-11-mut",
            new_title="Mutant",
        ),
        form_data={"component": "HC1", "mutations": "S2A N4Q", "rationale": ""},
        error="",
    )
    assert "Before" in html
    assert "After" in html
    assert "S2A N4Q" in html
    assert "Changed residues" in html
    assert "Sequence diff view" in html
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
