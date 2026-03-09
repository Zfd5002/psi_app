from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.routers import programs as programs_router
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_program_board_route_exists() -> None:
    route_keys = {
        (r.path, tuple(sorted(getattr(r, "methods", set()) or set())))
        for r in programs_router.router.routes
    }
    assert ("/programs/{program_id}/board", ("GET",)) in route_keys


def test_program_board_template_renders_sections() -> None:
    tpl = _env().get_template("programs/board.html")
    html = tpl.render(
        request=SimpleNamespace(),
        program=SimpleNamespace(id=1, name="P1"),
        board_filter="all",
        board_query="M-2",
        board_owner_filter="Dr X",
        board_urgency_filter="high",
        board_task_status_filter="open",
        board_due_filter="due_soon",
        board={
            "execution_rollup": {"in_progress_this_week": 1, "overdue": 2, "blocked": 1, "unassigned": 3},
            "groups": {
                "ready": [{"molecule_id": 2, "primary_id": "M-2", "status": "ready", "blocking_reason": "", "trend_signal": "improving", "missing_metrics": ["kd_nM"], "recommended_experiments": [{"metric_key": "kd_nM"}], "warnings": ["confirmation recommended"], "open_task_count": 2, "in_progress_task_count": 1, "top_next_task_label": "SPR (kd_nM)", "top_next_action": "Continue task: SPR (kd_nM)", "why_here": "Ready because required criteria are currently satisfied."}],
                "failed": [],
                "missing_data": [],
                "not_evaluated": [],
            }
        },
    )
    assert "Development Board" in html
    assert "READY" in html
    assert "FAILED CRITERIA" in html
    assert "MISSING DATA" in html
    assert "ASSESSMENT PENDING" in html
    assert "Program Summary" in html
    assert "Execution Panel" in html
    assert "In progress this week:" in html
    assert "> 1<" in html
    assert "Ready:" in html
    assert "> 1<" in html
    assert "/programs/1/board?filter=ready" in html
    assert "Search molecule ID" in html
    assert 'name="q"' in html
    assert "Apply task filters" in html
    assert 'name="owner"' in html
    assert 'name="urgency"' in html
    assert 'name="task_status"' in html
    assert 'name="due"' in html
    assert "/molecules/2" in html
    assert 'id="board-ready"' in html
    assert "count=1" in html
    assert "Status: Ready" in html
    assert "Tasks:" in html
    assert "open 2" in html
    assert "in progress 1" in html
    assert "next SPR (kd_nM)" in html
    assert "Why here: Ready because required criteria are currently satisfied." in html
    assert "Top next action:</b> Continue task: SPR (kd_nM)" in html
    assert "▲ improving" in html
    assert 'data-card-link="/molecules/2"' in html
    assert "Add missing measurement" in html
    assert "Create task" in html
    assert "Create task + start data entry" in html
    assert "/programs/1/tasks/create" in html
    assert "/programs/1/tasks/create-and-start-data" in html
    assert 'name="metric_key"' in html
    assert "/builder/exploration-task" in html
    assert "Create exploration task + variant" in html
    assert "/molecules/2#sequence-editor" in html
    assert "⚠ confirmation recommended" in html
