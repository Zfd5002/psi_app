from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def test_humanize_key_applies_acronyms_and_overrides() -> None:
    assert humanize_key("qc_mode") == "QC Mode"
    assert humanize_key("api_url") == "API URL"
    assert humanize_key("as_of_ts") == "As Of"


def test_humanize_state_and_path_token_are_deterministic() -> None:
    assert humanize_state("not_assessed") == "Not assessed by this surface."
    assert humanize_state("ready_for_scaleup_screen") == "Ready For Scaleup Screen"
    assert humanize_path_token("IN_VIVO_EFFICACY/NOD") == "In Vivo Efficacy / NOD"
    assert humanize_path_token("PK_PD/NONCOMP") == "PK/PD / NONCOMP"


def test_board_view_humanizes_known_snake_case_key() -> None:
    tpl = _env().get_template("reports/board_molecule_v3.html")
    html = tpl.render(
        molecule_board_display={
            "header": {},
            "conclusions": {},
            "batch_registry": [],
            "gate_summary": {},
            "fact_sheet": {"batch_labels": ["B-001"], "metric_rows": [{"metric_key": "as_of_ts", "metric_group": "Other", "cells": ["x"]}]},
            "comparability": {},
            "risk_qc": {},
            "scientist_notes": [],
        },
        policy_pin_summary=[],
        runtime_policy_versions={},
    )
    assert "As Of" in html


def test_technical_view_keeps_raw_key_for_auditability() -> None:
    tpl = _env().get_template("reports/_technical_audit.html")
    html = tpl.render(
        payload={"sections": {"as_of_ts": "2026-02-26"}, "metadata": {"report_type": "molecule_report"}},
        policy_pin_summary=[],
        rule_ids=[],
        measurement_key_citations=[],
        evidence_snapshot_refs=[],
        governance_warnings=[],
    )
    assert "as_of_ts" in html
