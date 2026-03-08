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
            "plan_count": 5,
            "recommended_plans": 3,
            "accepted_plans": 1,
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
        portfolio_trajectory=[
            {
                "program_id": 1,
                "program_name": "P1",
                "molecule_id": 7,
                "suggested_assay": "BLI",
                "metric_key": "kd_nM",
                "expected_readiness_gain": 1,
                "confidence_level": "high",
                "confidence_score": 0.81,
            }
        ],
        portfolio_claim_summary={
            "most_supported_claims": [{"claim_id": 4, "title": "Affinity claim", "supporting_count": 3}],
            "most_at_risk_claims": [{"claim_id": 5, "title": "Safety claim", "contradicting_count": 2}],
            "most_evidence_starved_claims": [{"claim_id": 6, "title": "Mechanism claim", "status": "hypothesis"}],
            "highest_task_burden_claims": [{"claim_id": 7, "title": "Readiness claim", "task_burden": 4}],
        },
        portfolio_plan_summary={
            "most_actionable_plans": [{"plan_id": 8, "title": "Readiness bundle", "score": 1.2}],
            "accepted_plans": [{"plan_id": 9, "title": "Claim bundle", "score": 0.9}],
            "awaiting_task_instantiation_plans": [{"plan_id": 8, "title": "Readiness bundle", "proposed_steps": 2}],
            "bottleneck_targeting_plans": [{"plan_id": 8, "title": "Readiness bundle"}],
        },
    )
    assert "Portfolio Intelligence" in html
    assert "Portfolio Summary" in html
    assert "Program Table" in html
    assert "Global Task Status" in html
    assert "Molecule Leaderboard" in html
    assert "Evidence Gap Report" in html
    assert "Portfolio Timeline" in html
    assert "Portfolio Trajectory Insights" in html
    assert "Portfolio Claim Insights" in html
    assert "Portfolio Plan Insights" in html
    assert "Affinity claim" in html
    assert "Readiness bundle" in html
    assert "kd_nM" in html
    assert "/molecules/7" in html
    assert "2026-03-02" in html
    assert "Tasks in progress:" in html
    assert "/programs/1" in html
    assert "🟢 progressing" in html
    assert "⚠ missing_metric_concentration:kd_nM" in html
    assert "1.75" in html
