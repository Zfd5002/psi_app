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


def test_decision_list_humanizes_decision_key() -> None:
    tpl = _env().get_template("decisions/list.html")
    html = tpl.render(
        snaps=[
            SimpleNamespace(
                id=3,
                decision_key="advance_to_in_vivo",
                is_superseded=0,
                program_id=1,
                molecule_id=2,
                batch_id=4,
                rules_version="v1",
                created_at="2026-03-09",
            )
        ],
        active_program=None,
    )
    assert "Assessment History" in html
    assert "Development Progression" in html
    assert "advance_to_in_vivo" not in html
