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


def test_builder_variant_set_routes_exist() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set())))) for r in builder_router.router.routes}
    assert ("/builder/variant-set", ("GET",)) in route_keys
    assert ("/builder/variant-set/draft", ("POST",)) in route_keys
    assert ("/builder/variant-set/create", ("POST",)) in route_keys
    assert ("/builder/variant-sets/{variant_set_id}", ("GET",)) in route_keys


def test_builder_index_renders_variant_set_entry() -> None:
    tpl = _env().get_template("builder/index.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
    )
    assert "Variant Set Builder" in html
    assert "/builder/variant-set" in html


def test_builder_variant_set_template_renders_family_type_selector() -> None:
    tpl = _env().get_template("builder/variant_set.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[SimpleNamespace(id=11, primary_id="M-11", title="Mol11")],
        parent_programs=[SimpleNamespace(id=1, name="P1")],
        parent_molecules_by_program={1: [{"id": 11, "primary_id": "M-11", "title": "Mol11"}]},
        parent_molecules_by_program_json='{"1":[{"id":11,"primary_id":"M-11","title":"Mol11"}]}',
        draft=None,
        form_data={},
        error="",
    )
    assert "Family type" in html
    assert 'name="family_type"' in html
    assert 'name="queued_component"' in html
    assert "mutation_panel" in html
    assert "scaffold_panel" in html


def test_builder_variant_set_template_shows_save_only_for_valid_draft() -> None:
    tpl = _env().get_template("builder/variant_set.html")
    html_valid = tpl.render(
        request=SimpleNamespace(),
        molecules=[],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=SimpleNamespace(
            errors=[],
            warnings=[],
            is_valid=True,
            set_name="SetA",
            family_type="mutation_panel",
            members=[
                SimpleNamespace(
                    sort_index=1,
                    member_label="N4Q",
                    member_summary="summary",
                    molecule_spec=SimpleNamespace(new_primary_id="M_104_N4Q"),
                    molecule_draft=SimpleNamespace(is_valid=True),
                )
            ],
        ),
        form_data={"family_type": "mutation_panel", "parent_molecule_id": 1, "set_name": "SetA", "naming_base": "M-104"},
        error="",
    )
    assert "Save variant family" in html_valid

    html_invalid = tpl.render(
        request=SimpleNamespace(),
        molecules=[],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=SimpleNamespace(
            errors=["bad mutation"],
            warnings=[],
            is_valid=False,
            set_name="SetA",
            family_type="mutation_panel",
            members=[],
        ),
        form_data={"family_type": "mutation_panel", "parent_molecule_id": 1, "set_name": "SetA", "naming_base": "M-104"},
        error="",
    )
    assert "Save variant family" not in html_invalid


def test_builder_variant_set_detail_template_renders_members() -> None:
    tpl = _env().get_template("builder/variant_set_detail.html")
    html = tpl.render(
        request=SimpleNamespace(),
        variant_set=SimpleNamespace(
            id=8,
            name="Panel A",
            builder_mode="mutation_panel",
            summary="3 variants",
            rationale="cleanup",
            created_at="2026-03-07T12:00:00Z",
        ),
        members=[
            {
                "sort_index": 1,
                "member_label": "N4Q",
                "molecule_id": 100,
                "primary_id": "M_104_N4Q",
                "title": "N4Q child",
                "parent_primary_id": "M-104",
                "derivation_type": "point_mutation",
                "member_summary": "N4Q",
            }
        ],
    )
    assert "Variant Family Review" in html
    assert "Panel A" in html
    assert "M_104_N4Q" in html
    assert "/molecules/100" in html
