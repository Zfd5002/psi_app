from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_cdr_builder_template_renders_inputs_and_draft_action() -> None:
    tpl = _env().get_template("builder/cdr_builder.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[],
        parent_programs=[SimpleNamespace(id=1, name="P1")],
        parent_molecules_by_program={1: [{"id": 10, "primary_id": "M10", "title": "Mol10"}]},
        parent_molecules_by_program_json='{"1":[{"id":10,"primary_id":"M10","title":"Mol10"}]}',
        draft=None,
        form_data={},
        error="",
    )
    assert "CDR Builder" in html
    assert 'action="/builder/cdr-builder/draft"' in html
    assert 'name="HCDR1"' in html
    assert 'name="LCDR3"' in html


def test_cdr_builder_template_renders_before_after_preview_block() -> None:
    tpl = _env().get_template("builder/cdr_builder.html")
    html = tpl.render(
        request=SimpleNamespace(),
        molecules=[],
        parent_programs=[],
        parent_molecules_by_program={},
        parent_molecules_by_program_json="{}",
        draft=SimpleNamespace(
            errors=[],
            warnings=["warn-1"],
            assumptions=["framework_preset=human_vh3_vk1"],
            preview_rows=[{"component": "HC1", "before": "AAAA", "after": "BBBB", "mutations": "HCDR1,HCDR2,HCDR3"}],
            changed_residues=[{"component": "HC1", "position": "2", "from": "A", "to": "B"}],
            components={"HC1": "BBBB"},
        ),
        form_data={},
        error="",
    )
    assert "Sequence reconstructed from CDRs using scaffold" in html
    assert "Before / After" in html
    assert "Inserted CDRs" in html
    assert "Sequence diff view" in html
    assert "Changed residues" in html
    assert "Assumptions" in html
