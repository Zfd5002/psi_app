from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_program_workflow_awaiting_data_link_includes_source_and_return() -> None:
    tpl = _env().get_template("programs/workflow.html")
    html = tpl.render(
        request=SimpleNamespace(),
        program=SimpleNamespace(id=7, name="P7"),
        ready_to_start=[],
        in_progress=[],
        blocked_tasks=[],
        awaiting_data_entry=[SimpleNamespace(id=33, molecule_id=9, suggested_assay="SPR", metric_key="kd_nM")],
        recently_completed=[],
        molecule_by_id={9: SimpleNamespace(primary_id="M-9")},
        source_rollup={},
    )
    assert "source=workflow" in html
    assert "return_to=/programs/7/workflow" in html
