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
                "decision_template": "molecule_report",
                "policy_version": "v0.2",
                "snapshot_id": 101,
                "generated_at": "2026-03-03T12:00:00",
            },
            "conclusions": {
                "readiness_status": "ready",
                "best_overall_batch": "B-002",
                "comparability_status": "comparable_full",
                "stability_status": "STABLE",
                "blockers": ["missing_pk"],
                "governance_warnings": ["none"],
                "executive_paragraph": "Readiness is ready.",
                "stability_rationale": ["Recent batch outcomes are not in conflict."],
            },
            "batch_registry": [
                {"batch_id": 2, "batch_label": "B-002", "batch_date": "2026-02-02", "producer": "unknown", "purpose_notes": "pilot", "coverage_summary": "SEC, Assay"},
                {"batch_id": 1, "batch_label": "B-001", "batch_date": "2026-02-01", "producer": "unknown", "purpose_notes": "screen", "coverage_summary": "SEC"},
            ],
            "gate_summary": {
                "best_batch_rows": [{"gate_key": "G1", "status": "pass", "primary_evidence": "e1", "notes": "n1"}],
                "per_batch_rows": [{"batch_label": "B-002", "overall": "ready", "fail_gates": [], "missing_gates": []}],
            },
            "fact_sheet": {
                "batch_labels": ["B-002", "B-001"],
                "metric_rows": [
                    {"metric_key": "ec50", "metric_group": "Assay", "cells": ["12 nM", "not run"]},
                    {"metric_key": "kd", "metric_group": "Assay", "cells": ["3 nM", "5 nM"]},
                ],
            },
            "comparability": {
                "effective_status": "comparable_full",
                "resolved_status": "comparable_full",
                "rule_id": "rule_comparable_full",
                "as_of_basis": "2026-03-03T00:00:00",
                "policy_ref": "v0.2",
                "governance_warnings": [],
            },
            "risk_qc": {"bullets": ["Missing required metrics: pk_auc"]},
            "scientist_notes": [{"author": "local-user", "timestamp": "2026-03-02T10:00:00", "scope": "B-002", "body": "Promising run."}],
        },
    )
    assert "Molecule Fact Sheet Header" in html
    assert "Conclusions" in html
    assert "Batch Registry" in html
    assert "Gate Summary" in html
    assert "Experimental Results Fact Sheet" in html
    assert "Comparability" in html
    assert "Risk &amp; QC Summary" in html
    assert "Scientist Notes" in html
    assert html.find("Ec50") < html.find("Kd")
