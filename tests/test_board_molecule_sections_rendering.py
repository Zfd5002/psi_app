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
        molecule_board_display={
            "header": {
                "molecule": "M1 (Mol 1)",
                "program": "program_id=1",
                "modality": "IgG",
                "generated_at": "2026-03-03T12:00:00",
            },
            "report_summary": {
                "most_complete_batch": "B-002",
                "stability_status": "STABLE",
                "top_required_present_count": 3,
                "top_total_present_count": 6,
                "executive_paragraph": "Most complete batch by measurement coverage is B-002.",
                "stability_rationale": ["Recent batch outcomes are not in conflict."],
            },
            "batch_registry": [
                {"batch_id": 2, "batch_label": "B-002", "batch_date": "2026-02-02", "producer": "unknown", "purpose_notes": "pilot", "coverage_summary": "SEC, Assay"},
                {"batch_id": 1, "batch_label": "B-001", "batch_date": "2026-02-01", "producer": "unknown", "purpose_notes": "screen", "coverage_summary": "SEC"},
            ],
            "fact_sheet": {
                "batch_labels": ["B-002", "B-001"],
                "metric_rows": [
                    {"metric_key": "ec50", "metric_group": "Assay", "cells": ["12 nM", "not run"]},
                    {"metric_key": "kd", "metric_group": "Assay", "cells": ["3 nM", "5 nM"]},
                ],
            },
            "coverage_summary": {"batch_count": 2, "record_count": 3, "measurement_count": 5, "required_metric_count": 2},
            "artifacts": {
                "items": [
                    {"artifact_type": "SEC", "batch_label": "B-002", "created_at": "2026-03-02", "title": "SEC trace", "links": [{"label": "Data record", "url": "/data/7"}]}
                ]
            },
            "scientist_notes": [{"author": "local-user", "timestamp": "2026-03-02T10:00:00", "scope": "B-002", "body": "Promising run."}],
        },
    )
    assert "Molecule Overview" in html
    assert "Report Summary" in html
    assert "Batch Registry" in html
    assert "Experimental Results Fact Sheet" in html
    assert "Coverage Summary" in html
    assert "Artifacts" in html
    assert "Scientist Notes" in html
    assert html.find("Ec50") < html.find("Kd")
