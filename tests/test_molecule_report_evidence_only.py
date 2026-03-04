from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Batch, DataRecord, Molecule, Program
from psi.services.report_engine import generate_molecule_report_v0, load_report_run_payload
from psi.services.reports_v3 import build_molecule_board_display_from_payload
from psi.web.ui_labels import humanize_key, humanize_path_token, humanize_state


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS data_measurements (
                    id INTEGER PRIMARY KEY,
                    data_record_id INTEGER NOT NULL,
                    metric_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value_num REAL,
                    value_text TEXT,
                    unit TEXT,
                    qc_flag TEXT,
                    ignore_for_model INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT
                )
                """
            )
        )
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    env.filters["humanize_state"] = humanize_state
    env.filters["humanize_path_token"] = humanize_path_token
    return env


def _seed_and_generate_without_snapshots():
    eng, SessionTmp = _mkdb()
    db = SessionTmp()
    p = Program(name="P-evidence", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
    db.add(p)
    db.flush()
    m = Molecule(
        program_id=int(p.id),
        primary_id="EX-INT-012",
        title="Molecule 15",
        created_at=datetime(2026, 3, 3),
        updated_at=datetime(2026, 3, 3),
    )
    db.add(m)
    db.flush()
    b = Batch(
        molecule_id=int(m.id),
        batch_id="M15-B1",
        title="Batch 1",
        created_at=datetime(2026, 3, 3, 9, 0, 0),
        updated_at=datetime(2026, 3, 3, 9, 0, 0),
    )
    db.add(b)
    db.flush()
    rec = DataRecord(
        program_id=int(p.id),
        molecule_id=int(m.id),
        batch_id=int(b.id),
        domain="in_vitro",
        data_type="binding",
        method="spr",
        title="SPR run",
        notes="note-a",
        run_date="2026-03-03",
        created_at=datetime(2026, 3, 3, 10, 0, 0),
        updated_at=datetime(2026, 3, 3, 10, 0, 0),
    )
    db.add(rec)
    db.flush()
    db.execute(
        text(
            """
            INSERT INTO data_measurements
            (data_record_id, metric_key, name, value_num, value_text, unit, qc_flag, ignore_for_model, created_at)
            VALUES
            (:rid, 'ec50', 'ec50', 12.3, NULL, 'nM', 'approved', 0, '2026-03-03T10:00:00')
            """
        ),
        {"rid": int(rec.id)},
    )
    db.commit()
    row = generate_molecule_report_v0(
        db,
        molecule_id=int(m.id),
        as_of=datetime(2026, 3, 3, 11, 0, 0),
        policy_pins={"report_policy": "v0"},
    )
    payload = load_report_run_payload(row)
    return eng, db, row, payload


def test_molecule_report_evidence_only_has_no_di_sections() -> None:
    eng, db, row, payload = _seed_and_generate_without_snapshots()
    try:
        sections = payload.get("sections", {})
        assert set(sections.keys()) == {"artifacts", "fact_sheet", "identity_context", "reproducibility_appendix"}
        assert payload.get("metadata", {}).get("snapshot_coverage") == []
    finally:
        db.close()
        eng.dispose()


def test_molecule_report_renders_without_snapshots() -> None:
    eng, db, row, payload = _seed_and_generate_without_snapshots()
    try:
        board = build_molecule_board_display_from_payload(row=row, payload=payload)
        assert board.get("fact_sheet", {}).get("metric_rows")
        tpl = _env().get_template("reports/detail.html")
        html = tpl.render(
            report_run=SimpleNamespace(id=int(row.id), report_type="molecule_report", as_of=row.as_of, created_at=row.created_at),
            payload=payload,
            subject_ids=[1],
            snapshot_coverage=[],
            identity_summary="EX-INT-012 (Molecule 15)",
            board_template_name="reports/board_molecule_v3.html",
            board_narrative={},
            molecule_board_display=board,
            is_pdf=True,
        )
        assert "Experimental Results Fact Sheet" in html
    finally:
        db.close()
        eng.dispose()


def test_molecule_report_board_template_no_di_strings() -> None:
    eng, db, row, payload = _seed_and_generate_without_snapshots()
    try:
        board = build_molecule_board_display_from_payload(row=row, payload=payload)
        tpl = _env().get_template("reports/board_molecule_v3.html")
        html = tpl.render(molecule_board_display=board)
        for token in [
            "Readiness",
            "Comparability",
            "Gate",
            "Risk flags",
            "Snapshot ID",
            "Policy Version",
            "missing_policy_pins_or_hashes",
        ]:
            assert token not in html
    finally:
        db.close()
        eng.dispose()


def test_experimental_results_header_alignment_hook_present() -> None:
    tpl = _env().get_template("reports/board_molecule_v3.html")
    html = tpl.render(
        molecule_board_display={
            "header": {},
            "report_summary": {},
            "batch_registry": [],
            "fact_sheet": {
                "batch_labels": ["B1"],
                "metric_rows": [{"metric_key": "ec50", "metric_group": "Assay", "cells": ["12 nM"]}],
            },
            "coverage_summary": {},
            "scientist_notes": [],
        }
    )
    assert "fact-sheet-matrix" in html


def test_report_detail_hides_technical_audit_label_for_scientist_view() -> None:
    eng, db, row, payload = _seed_and_generate_without_snapshots()
    try:
        board = build_molecule_board_display_from_payload(row=row, payload=payload)
        tpl = _env().get_template("reports/detail.html")
        html = tpl.render(
            report_run=SimpleNamespace(id=int(row.id), report_type="molecule_report", as_of=row.as_of, created_at=row.created_at),
            payload=payload,
            subject_ids=[1],
            snapshot_coverage=[],
            identity_summary="EX-INT-012 (Molecule 15)",
            board_template_name="reports/board_molecule_v3.html",
            board_narrative={},
            molecule_board_display=board,
            is_pdf=False,
            policy_pin_summary=[],
            governance_warnings=[],
            rule_ids=[],
            measurement_key_citations=[],
            evidence_snapshot_refs=[],
        )
        assert "Technical Audit" not in html
        assert "Structured Report Payload" in html
        assert 'aria-hidden="true"' in html
        assert 'const key = "psi.view.report_detail_mode";' in html
        assert 'techPanel.style.display = "block";' in html
        assert "data-report-governance-toggle" in html
        assert 'data-report-panel="governance"' in html
    finally:
        db.close()
        eng.dispose()


def test_report_detail_governance_toggle_hidden_in_pdf_mode() -> None:
    eng, db, row, payload = _seed_and_generate_without_snapshots()
    try:
        board = build_molecule_board_display_from_payload(row=row, payload=payload)
        tpl = _env().get_template("reports/detail.html")
        html = tpl.render(
            report_run=SimpleNamespace(id=int(row.id), report_type="molecule_report", as_of=row.as_of, created_at=row.created_at),
            payload=payload,
            subject_ids=[1],
            snapshot_coverage=[],
            identity_summary="EX-INT-012 (Molecule 15)",
            board_template_name="reports/board_molecule_v3.html",
            board_narrative={},
            molecule_board_display=board,
            is_pdf=True,
            policy_pin_summary=[],
            governance_warnings=[],
            rule_ids=[],
            measurement_key_citations=[],
            evidence_snapshot_refs=[],
        )
        assert "data-report-governance-toggle" not in html
        assert "Governance Payload Detail" not in html
        assert 'data-report-panel="governance"' not in html
    finally:
        db.close()
        eng.dispose()
