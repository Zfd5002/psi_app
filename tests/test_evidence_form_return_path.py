from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_evidence_form_renders_return_to_controls() -> None:
    tpl = _env().get_template("evidence/form.html")
    html = tpl.render(
        request=SimpleNamespace(),
        ev=None,
        programs=[SimpleNamespace(id=1, name="P1")],
        molecules=[],
        batches=[],
        domains=["Biological"],
        domain_evidence_types={"Biological": ["binding_support"]},
        prefill={"program_id": 1, "molecule_id": None, "batch_id": None},
        return_to="/programs/1/workflow",
    )
    assert 'name="return_to"' in html
    assert '/programs/1/workflow' in html
    assert "Return to Prior Context" in html

