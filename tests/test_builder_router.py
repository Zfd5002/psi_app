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
    assert "/molecules/11" in html


def test_builder_clone_template_has_preview_first_actions() -> None:
    tpl = _env().get_template("builder/clone.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        draft=None,
        form_data={},
        error="",
    )
    assert "Build draft" in html
    assert 'action="/builder/clone/draft"' in html


def test_builder_point_mutation_template_has_preview_first_actions() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        draft=None,
        form_data={},
        error="",
    )
    assert "Build draft" in html
    assert 'action="/builder/point-mutation/draft"' in html


def test_builder_point_mutation_template_renders_before_after_preview() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        draft=SimpleNamespace(
            errors=[],
            warnings=[],
            parent_primary_id="M-11",
            derivation_type="point_mutation",
            preview_rows=[{"component": "HC1", "before": "MSGN", "after": "MAGQ", "mutations": "S2A N4Q"}],
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
    assert 'action="/builder/point-mutation/create"' in html
