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


def test_program_workflow_template_shows_recent_learning_sections() -> None:
    tpl = _env().get_template("programs/workflow.html")
    html = tpl.render(
        request=SimpleNamespace(),
        program=SimpleNamespace(id=1, name="P1"),
        ready_to_start=[],
        in_progress=[],
        blocked_tasks=[],
        awaiting_data_entry=[],
        recently_completed=[],
        molecule_by_id={},
        source_rollup={},
        recent_data_records=[SimpleNamespace(id=10, molecule_id=None, title="Run A")],
        recent_evidence=[SimpleNamespace(id=20, evidence_type="binding_support", strength=3)],
        pending_interpretation=[SimpleNamespace(id=10, molecule_id=None, batch_id=None, title="Run A")],
    )
    assert "Recently Captured Learning" in html
    assert "Recent Results" in html
    assert "Recent Evidence" in html
    assert "Results Awaiting Interpretation" in html
    assert "/data/10" in html
    assert "/evidence/20" in html
