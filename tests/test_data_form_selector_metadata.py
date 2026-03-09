from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_data_form_renders_program_molecule_batch_option_metadata() -> None:
    tpl = _env().get_template("partials/data/form_core_fields.html")
    html = tpl.render(
        record=None,
        prefill={"program_id": 10, "molecule_id": 20, "batch_id": 30, "domain": "", "data_type": "", "method": "", "title": ""},
        programs=[SimpleNamespace(id=10, name="Program-10")],
        molecules=[SimpleNamespace(id=20, primary_id="M-20", program_id=10)],
        batches=[SimpleNamespace(id=30, batch_id="B-30", molecule_id=20, molecule=SimpleNamespace(program_id=10))],
        domains=["Biological"],
    )
    assert 'id="programSel"' in html
    assert 'id="moleculeSel"' in html
    assert 'id="batchSel"' in html
    assert 'data-program-id="10"' in html
    assert 'data-molecule-id="20"' in html


def test_data_form_js_contains_scope_sync_logic() -> None:
    js = (Path(__file__).resolve().parents[1] / "psi" / "web" / "static" / "data_form.js").read_text(encoding="utf-8")
    assert "syncScope" in js
    assert "programSel.addEventListener('change'" in js
    assert "moleculeSel.addEventListener('change'" in js
    assert "batchSel.addEventListener('change'" in js
