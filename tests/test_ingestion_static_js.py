from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_data_form_uses_static_js_and_config_payload() -> None:
    tpl = _env().get_template("data/form.html")
    html = tpl.render(
        request=SimpleNamespace(query_params={}),
        record=None,
        programs=[SimpleNamespace(id=1, name="P1")],
        molecules=[],
        batches=[],
        domains=["Biological"],
        prefill={"program_id": 1, "molecule_id": None, "batch_id": None},
        return_to="/programs/1/workflow",
    )
    assert 'id="dataFormConfig"' in html
    assert '/static/data_form.js' in html


def test_evidence_form_uses_static_js_and_config_payload() -> None:
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
        cited_ids=[],
    )
    assert 'id="evidenceFormConfig"' in html
    assert '/static/evidence_form.js' in html
