from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psi.web.ui_labels import humanize_key


def test_board_comparison_template_renders_alignment_matrix() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    tpl = env.get_template("reports/board_comparison_v3.html")
    html = tpl.render(
        board_narrative={
            "headline": "Comparison",
            "status_rows": [],
            "what_this_means": [],
            "evidence_status": [],
            "determinations": [],
            "next_steps": [],
        },
        payload={
            "sections": {
                "program_set": {"rows": [{"program_id": 20, "molecule_count": 2}, {"program_id": 10, "molecule_count": 1}]},
                "portfolio_posture_comparison": {"rows": [{"program_id": 10, "posture_state": "on_track"}, {"program_id": 20, "posture_state": "at_risk"}]},
                "molecule_set": {"rows": [{"molecule_id": 1, "primary_id": "M1", "stage": "ready", "program_id": 10}]},
                "reproducibility_appendix": {"measurement_keys": ["ec50", "kd"]},
                "comparability_surface": {"assessments": [{"cited_measurement_keys": ["ec50"]}]},
                "resource_implications": {"rows": []},
            }
        },
    )
    assert "Lineage Comparison" in html
    assert "Alignment Matrix" in html
    assert "ec50" in html
    assert "✓" in html
    assert "Portfolio / Program Posture Comparison" in html
    assert "program_id=10" in html and "program_id=20" in html
    assert html.find("program_id=10") < html.find("program_id=20")
    assert "Not assessed by this report schema." in html
