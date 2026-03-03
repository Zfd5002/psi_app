from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psi.web.ui_labels import humanize_key


def test_board_narrative_template_surfaces_determination_citations() -> None:
    template_root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_root)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["humanize_key"] = humanize_key
    tpl = env.get_template("reports/_board_narrative.html")
    html = tpl.render(
        board_narrative={
            "headline": "Molecule report for M1",
            "status_rows": [],
            "what_this_means": [],
            "evidence_status": [],
            "next_steps": [],
            "determinations": [
                {
                    "title": "Comparability",
                    "outcome": "not_assessed",
                    "rule_id": "rule_not_assessed_default",
                    "snapshot_ids": ["101", "202"],
                    "measurement_keys": ["ec50", "kd"],
                    "rationale": "policy_rule_match",
                    "missing_inputs": {"required_measurement_keys_missing": ["kd"]},
                }
            ],
        },
        payload={"sections": {"reproducibility_appendix": {"measurement_keys": ["ec50", "kd"]}}},
    )
    assert "rule_not_assessed_default" in html
    assert "101, 202" in html
    assert "ec50" in html and "kd" in html
