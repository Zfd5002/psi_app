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


def test_program_narrative_template_renders_sections() -> None:
    tpl = _env().get_template("programs/narrative.html")
    html = tpl.render(
        request=SimpleNamespace(),
        program=SimpleNamespace(id=1, name="Program A"),
        narrative={
            "scientific_thesis": "Thesis text",
            "current_state_summary": "Current state",
            "overall_stage": "execution_focus",
            "confidence_summary": "moderate",
            "strongest_support": ["Support 1"],
            "major_uncertainties": ["Uncertainty 1"],
            "active_risks": ["Risk 1"],
            "next_milestone": "Milestone A",
            "milestone_rationale": "Because",
            "active_plans": [{"plan_id": 4, "title": "Plan 4", "plan_type": "readiness_advancement", "status": "recommended"}],
            "top_trajectory": [{"suggested_assay": "SPR", "metric_key": "kd_nM", "expected_readiness_gain": 1}],
            "narrative_anchor_blocks": [{"title": "Claim anchors", "summary": "1 leading claim"}],
            "narrative_links": {
                "top_claim_links": [{"claim_id": 2, "label": "Claim 2"}],
                "top_plan_links": [{"plan_id": 4, "label": "Plan 4"}],
                "top_trajectory_links": [{"molecule_id": 9, "metric_key": "kd_nM", "assay": "SPR"}],
            },
            "milestone_framing": {
                "what_is_proven": ["Supported claims: 1"],
                "what_remains_to_prove": ["Missing-data molecules: 2"],
                "what_would_unlock_next_milestone": ["Recommended plans to execute: 1"],
                "what_is_underway": ["Active plans: 2"],
            },
        },
    )
    assert "Program Narrative" in html
    assert "Scientific Thesis" in html
    assert "Current State" in html
    assert "Major Uncertainties" in html
    assert "Next Milestone" in html
    assert "Evidence Anchors" in html
    assert "Milestone Framing" in html
    assert "What is proven" in html
    assert "/claims/2" in html
    assert "/plans/4" in html
    assert "/programs/1/narrative/export" in html


def test_program_narrative_template_brief_mode_renders_compact_block() -> None:
    tpl = _env().get_template("programs/narrative.html")
    html = tpl.render(
        request=SimpleNamespace(),
        program=SimpleNamespace(id=1, name="Program A"),
        narrative_brief=True,
        narrative={
            "scientific_thesis": "Thesis text",
            "current_state_summary": "Current state",
            "active_risks": ["Risk 1"],
            "next_milestone": "Milestone A",
        },
    )
    assert "Leadership Brief" in html
    assert "Switch to full" in html
