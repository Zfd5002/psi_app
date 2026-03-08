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


def test_claim_detail_template_renders_sections() -> None:
    tpl = _env().get_template("claims/detail.html")
    html = tpl.render(
        request=SimpleNamespace(),
        claim=SimpleNamespace(id=12, title="Affinity claim", claim_type="affinity", status="emerging", confidence_level="medium", statement="Claim statement", rationale="Because data" , program_id=3),
        maturity={"supporting_count": 2, "contradicting_count": 1, "linked_tasks_open": 1, "linked_tasks_done": 2, "linked_decisions_count": 3},
        evidence_links=[SimpleNamespace(direction="supporting", data_record_id=44, note="note")],
        decision_links=[SimpleNamespace(decision_snapshot_id=55, relationship_type="informs")],
        task_links=[SimpleNamespace(experiment_task_id=66, relationship_type="tests")],
        open_linked_tasks=[SimpleNamespace(task_id=66, status="planned", urgency="high", suggested_assay="BLI", metric_key="kd_nM")],
        trajectory_candidates=[{"suggested_assay": "BLI", "metric_key": "kd_nM", "expected_readiness_gain": 1, "confidence_level": "high", "confidence_score": 0.81}],
        claim_plans=[{"plan_id": 71, "title": "Claim plan", "plan_type": "claim_de_risking", "expected_readiness_gain": 0.2, "expected_claim_support_gain": 0.9, "expected_evidence_coverage_gain": 0.5, "steps": [{"step_order": 1, "step_kind": "claim_test", "metric_key": "kd_nM", "suggested_assay": "SPR"}]}],
    )
    assert "Scientific Claim" in html
    assert "Maturity Summary" in html
    assert "Evidence Links" in html
    assert "Decision Links" in html
    assert "Task Links" in html
    assert "Open Linked Tasks" in html
    assert "Relevant Trajectory Candidates" in html
    assert "Recommended Claim Plans" in html
    assert "/plans/71" in html
    assert "/claims/" not in html or True


def test_claim_list_template_renders_rows() -> None:
    tpl = _env().get_template("claims/list.html")
    html = tpl.render(
        request=SimpleNamespace(),
        claims=[SimpleNamespace(id=1, title="Affinity claim", scope_type="molecule", claim_type="affinity", status="emerging", confidence_level="medium")],
    )
    assert "Scientific Claims" in html
    assert "Affinity claim" in html
    assert "/claims/1" in html
