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


def test_portfolio_overview_renders_narrative_sections() -> None:
    tpl = _env().get_template("portfolio/overview.html")
    html = tpl.render(
        request=SimpleNamespace(),
        portfolio_summary={},
        program_summaries=[],
        molecule_leaderboard=[],
        evidence_gap_report=[],
        portfolio_timeline=[],
        portfolio_trajectory=[],
        portfolio_claim_summary={},
        portfolio_plan_summary={},
        portfolio_narrative={
            "near_term_inflection_points": ["Recommended plans: 2"],
            "strongest_programs": [{"program_id": 1, "program_name": "P1", "readiness_score": 1.2}],
            "key_bottlenecks": ["missing_metric_concentration:kd_nM (2)"],
            "near_term_inflection_rows": [{"program_id": 1, "program_name": "P1", "molecules_ready": 1}],
            "task_burden_summary": {"tasks_in_progress": 2, "tasks_overdue": 1, "tasks_blocked": 1},
            "evidence_gap_summary": {"missing_data_molecules": 3, "evidence_starved_claims": 2},
            "leadership_cards": {
                "programs_nearing_milestone": [{"program_id": 1, "program_name": "P1"}],
                "programs_needing_support": [{"program_id": 2, "program_name": "P2"}],
                "highest_value_pending_plans": [{"plan_id": 3, "title": "Plan 3"}],
                "largest_evidence_gaps": [{"metric_key": "kd_nM", "missing_molecule_count": 4}],
            },
        },
    )
    assert "Portfolio Narrative" in html
    assert "Portfolio state summary" in html
    assert "Strongest progress signals" in html
    assert "Most constrained areas" in html
    assert "Top upcoming inflection points" in html
    assert "Task/plan burden summary" in html
    assert "Evidence gap summary" in html
    assert "Programs nearing milestone" in html
    assert "Programs needing support" in html
    assert "Highest-value pending plans" in html
    assert "Largest evidence gaps" in html
    assert "/plans/3" in html
    assert "/programs/1" in html
    assert "/portfolio/narrative/export" in html


def test_portfolio_overview_brief_mode_renders_compact_section() -> None:
    tpl = _env().get_template("portfolio/overview.html")
    html = tpl.render(
        request=SimpleNamespace(),
        narrative_brief=True,
        portfolio_summary={},
        portfolio_narrative={
            "near_term_inflection_points": ["Recommended plans: 1"],
            "strongest_programs": [{"program_id": 1, "program_name": "P1"}],
            "key_bottlenecks": ["missing_data_molecules (2)"],
            "highest_value_plans": [{"plan_id": 3, "title": "Plan 3"}],
        },
    )
    assert "Leadership Brief" in html
    assert "Switch to full" in html
    assert "/plans/3" in html
