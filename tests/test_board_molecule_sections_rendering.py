from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def test_board_molecule_template_renders_key_v3_section_headings() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    tpl = env.get_template("reports/board_molecule_v3.html")
    html = tpl.render(
        board_narrative={
            "headline": "Molecule report for M1",
            "status_rows": [],
            "what_this_means": [],
            "evidence_status": [],
            "determinations": [],
            "next_steps": [],
        },
        payload={
            "sections": {
                "mechanistic_evidence_map": {"used_by_metric": {"ec50": [1]}},
                "risk_profile": {"risk_flags_enriched": [{"severity": "high", "key": "agg", "description": "Aggregation"}]},
                "confidence_decomposition": {"confidence": {"overall": "medium"}, "state_of_evidence_summary": {"count": 2}},
                "reproducibility_appendix": {"policy_pins": {"a": "b"}, "measurement_keys": ["ec50"], "cited_snapshot_ids": [101]},
            }
        },
    )
    assert "Mechanistic Evidence Map" in html
    assert "Risk Profile" in html
    assert "Confidence Decomposition" in html
    assert "Reproducibility Appendix" in html
