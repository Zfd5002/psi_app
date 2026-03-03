from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def test_board_program_template_renders_posture_summary_counts() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    tpl = env.get_template("reports/board_program_v3.html")
    html = tpl.render(
        board_narrative={
            "headline": "Program report",
            "status_rows": [],
            "what_this_means": [],
            "evidence_status": [],
            "determinations": [],
            "next_steps": [],
        },
        payload={
            "sections": {
                "molecule_overview_table": {
                    "rows": [
                        {"molecule_id": 1, "stage": "ready", "high_severity_risk_present": True},
                        {"molecule_id": 2, "stage": "blocked", "high_severity_risk_present": False},
                        {"molecule_id": 3, "stage": "not_assessed", "high_severity_risk_present": False},
                    ]
                }
            }
        },
        policy_pin_summary=[],
        runtime_policy_versions={},
    )
    assert "Portfolio Posture Summary" in html
    assert "Total molecules" in html
    assert ">3<" in html
