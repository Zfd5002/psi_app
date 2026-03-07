from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.ui_labels import humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_state"] = humanize_state
    return env


def test_clone_template_has_program_to_molecule_cascade_selectors() -> None:
    tpl = _env().get_template("builder/clone.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[],
        parent_programs=[SimpleNamespace(id=1, name="P1")],
        parent_molecules_by_program={1: [{"id": 11, "primary_id": "M-11", "title": "Mol11"}]},
        parent_molecules_by_program_json='{"1":[{"id":11,"primary_id":"M-11","title":"Mol11"}]}',
        draft=None,
        form_data={},
        error="",
    )
    assert 'id="builder_parent_program"' in html
    assert 'id="builder_parent_molecule"' in html
    assert 'id="builder_clear_selection"' in html
    assert 'id="builder_selected_parent_card"' in html
    assert "renderMolecules" in html


def test_point_mutation_template_has_program_to_molecule_cascade_selectors() -> None:
    tpl = _env().get_template("builder/point_mutation.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[],
        parent_programs=[SimpleNamespace(id=1, name="P1")],
        parent_molecules_by_program={1: [{"id": 11, "primary_id": "M-11", "title": "Mol11"}]},
        parent_molecules_by_program_json='{"1":[{"id":11,"primary_id":"M-11","title":"Mol11"}]}',
        draft=None,
        form_data={},
        error="",
    )
    assert 'id="builder_parent_program"' in html
    assert 'id="builder_parent_molecule"' in html
    assert 'id="builder_clear_selection"' in html
    assert 'id="builder_selected_parent_card"' in html
    assert "renderMolecules" in html
