from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psi.web.ui_labels import humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_state"] = humanize_state
    return env


def test_portfolio_overview_template_sections() -> None:
    tpl = _env().get_template("portfolio/overview.html")
    html = tpl.render(
        request=SimpleNamespace(),
        portfolio_summary={
            "program_count": 2,
            "molecule_count": 10,
            "task_count": 8,
            "overdue_tasks": 2,
            "blocked_tasks": 1,
            "tasks_in_progress": 3,
            "tasks_overdue": 2,
            "tasks_blocked": 1,
            "tasks_unassigned": 4,
            "ready_molecules": 3,
            "missing_data_molecules": 4,
        },
        program_summaries=[
            {
                "program_id": 1,
                "program_name": "P1",
                "heat_emoji": "🟢",
                "heat_label": "progressing",
                "readiness_score": 1.75,
                "molecules_ready": 2,
                "molecules_failed": 1,
                "molecules_missing_data": 1,
                "open_tasks": 3,
                "overdue_tasks": 1,
                "blocked_tasks": 0,
                "bottleneck_badges": ["missing_metric_concentration:kd_nM"],
            }
        ],
        molecule_leaderboard=[
            {
                "molecule_id": 7,
                "primary_id": "M-7",
                "program_id": 1,
                "status": "ready",
                "completed_evidence_count": 4,
                "missing_metrics_count": 0,
                "leaderboard_score": 3.8,
            }
        ],
        evidence_gap_report=[
            {"metric_key": "kd_nM", "missing_molecule_count": 12},
        ],
        portfolio_timeline=[
            {"week_start": "2026-03-02", "tasks_completed": 5, "tasks_created": 7, "evidence_created": 4},
        ],
    )
    assert "Portfolio Intelligence" in html
    assert "Portfolio Summary" in html
    assert "Program Table" in html
    assert "Global Task Status" in html
    assert "Molecule Leaderboard" in html
    assert "Evidence Gap Report" in html
    assert "Portfolio Timeline" in html
    assert "kd_nM" in html
    assert "/molecules/7" in html
    assert "2026-03-02" in html
    assert "Tasks in progress:" in html
    assert "/programs/1" in html
    assert "🟢 progressing" in html
    assert "⚠ missing_metric_concentration:kd_nM" in html
    assert "1.75" in html
