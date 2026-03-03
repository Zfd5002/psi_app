from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def test_board_comparison_template_renders_alignment_matrix() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
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
                "molecule_set": {"rows": [{"molecule_id": 1, "primary_id": "M1", "stage": "ready", "program_id": 10}]},
                "reproducibility_appendix": {"measurement_keys": ["ec50", "kd"]},
                "comparability_surface": {"assessments": [{"cited_measurement_keys": ["ec50"]}]},
            }
        },
    )
    assert "Lineage Comparison" in html
    assert "Alignment Matrix" in html
    assert "ec50" in html
    assert "✓" in html
