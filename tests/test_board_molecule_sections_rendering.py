from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def test_board_molecule_template_renders_key_v3_section_headings() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
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
                "scientific_summary": {
                    "status": "assessed",
                    "domains": [
                        {
                            "domain": "Binding",
                            "rows": [{"metric_key": "kd", "label": "KD", "value_display": "1 cited", "unit": "nM", "n": 1, "status": "present"}],
                        }
                    ],
                },
                "experimental_gaps": {"blockers": ["missing_pk"], "next_best_experiments": [{"label": "Run PK repeat"}]},
                "reproducibility_appendix": {"policy_pins": {"a": "b"}, "measurement_keys": ["ec50"], "cited_snapshot_ids": [101]},
            }
        },
    )
    assert "Mechanistic Evidence Map" in html
    assert "Risk Profile" in html
    assert "Confidence Decomposition" in html
    assert "Scientific Summary" in html
    assert "Binding" in html
    assert "Experimental Gaps" in html
    assert "Run PK repeat" in html
    assert "Reproducibility Appendix" in html
