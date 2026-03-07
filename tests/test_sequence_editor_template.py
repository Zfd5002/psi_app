from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_sequence_editor_partial_renders_interactive_residues() -> None:
    tpl = _env().get_template("molecules/_sequence_editor.html")
    html = tpl.render(
        request=SimpleNamespace(),
        sequence_editor_annotations=[
            {
                "component_id": 1,
                "component_role": "HC1",
                "sequence_length": 3,
                "residues": [
                    {"component_role": "HC1", "component_id": 1, "position": 1, "aa": "A", "region": "VH", "numbering_label": "H1"},
                    {"component_role": "HC1", "component_id": 1, "position": 2, "aa": "B", "region": "VH", "numbering_label": "H2"},
                ],
            }
        ],
    )
    assert "Sequence Editor" in html
    assert 'class="seq-residue"' in html
    assert 'data-position="1"' in html
    assert 'data-region="VH"' in html
    assert 'id="seq_mutation_queue"' in html
    assert 'id="seq_queue_clear"' in html
    assert 'id="seq_direct_mutations"' in html
    assert 'id="seq_direct_apply"' in html
    assert 'id="seq_preview_original"' in html
    assert 'id="seq_preview_edited"' in html
    assert 'action="/builder/point-mutation/draft"' in html
    assert 'id="seq_to_builder_mutations"' in html
    assert 'action="/builder/variant-set/draft"' in html
    assert 'id="seq_to_variant_mutation_tokens"' in html
    assert 'id="seq_to_variant_explicit_combos"' in html
