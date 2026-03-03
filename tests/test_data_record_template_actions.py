from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


class _Req:
    query_params = {}

    @staticmethod
    def url_for(name: str, **path_params) -> str:
        rid = int(path_params.get("record_id", 0))
        if name == "approve_record_qc":
            return f"/data/{rid}/qc/approve"
        if name == "reject_record_qc":
            return f"/data/{rid}/qc/reject"
        return "/"


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_data_detail_template_renders_entry_approve_reject_buttons() -> None:
    tpl = _env().get_template("data/detail.html")
    html = tpl.render(
        request=_Req(),
        record=SimpleNamespace(
            id=7,
            title="DR",
            domain="Biological",
            data_type="Binding",
            method="BLI",
            program=SimpleNamespace(id=1, name="P1"),
            program_id=1,
            molecule=None,
            molecule_id=None,
            batch=None,
            batch_id=None,
            run_date=None,
            notes="",
            params_json="{}",
            results_json="{}",
        ),
        measurements=[],
        qc_by_measurement_id={},
        file_links=[],
        files_by_id={},
        evidence_citing=[],
        audits=[],
    )
    assert "/data/7/qc/approve" in html
    assert "/data/7/qc/reject" in html
    assert "Approve entry" in html
    assert "Reject entry" in html


def test_data_form_template_renders_save_cancel_approve_reject_for_edit() -> None:
    tpl = _env().get_template("data/form.html")
    html = tpl.render(
        request=SimpleNamespace(query_params={"return_to": "/programs/1"}),
        record=SimpleNamespace(id=11, program_id=1, molecule_id=None, batch_id=None, run_date="", domain="Biological", data_type="Binding", method="BLI", title="DR", params_json="{}", results_json="{}", notes=""),
        programs=[SimpleNamespace(id=1, name="P1")],
        molecules=[],
        batches=[],
        domains=["Biological"],
        prefill={},
    )
    assert "Save" in html
    assert "Approve" in html
    assert "Reject" in html
    assert "Cancel" in html
    assert "Apply defaults to all rows" in html
    assert 'name="action_intent"' in html
