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


def test_plan_detail_template_renders() -> None:
    tpl = _env().get_template("plans/detail.html")
    html = tpl.render(
        request=SimpleNamespace(),
        plan=SimpleNamespace(id=2, title="Plan", plan_type="readiness_advancement", status="recommended", scope_type="molecule", program_id=3, molecule_id=5, claim_id=None, rationale="Because", expected_readiness_gain=1.0, expected_claim_support_gain=0.5, expected_evidence_coverage_gain=0.7),
        plan_score=1.234,
        effort_estimate=3,
        steps=[SimpleNamespace(step_order=1, step_kind="experiment", suggested_assay="SPR", metric_key="kd_nM", status="proposed", linked_experiment_task_id=None)],
    )
    assert "Scientific Plan" in html
    assert "Ordered Steps" in html
    assert "/programs/3" in html
    assert "/molecules/5" in html


def test_plan_list_template_renders() -> None:
    tpl = _env().get_template("plans/list.html")
    html = tpl.render(
        request=SimpleNamespace(),
        plans=[SimpleNamespace(id=3, title="Readiness bundle", plan_type="readiness_advancement", status="recommended", scope_type="molecule", expected_readiness_gain=1.0, expected_claim_support_gain=0.2, expected_evidence_coverage_gain=0.4)],
    )
    assert "Scientific Plans" in html
    assert "Readiness bundle" in html
    assert "/plans/3" in html
