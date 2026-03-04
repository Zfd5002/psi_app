from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Batch, DataRecord, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.report_engine import generate_molecule_report_v0, generate_program_report_v0, load_report_run_payload
from psi.services.v3_narrative import render_molecule_narrative, render_program_narrative


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


def test_molecule_narrative_measurements_gracefully_handles_evidence_only_payload() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            program = Program(name="P1", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(program)
            db.commit()
            db.refresh(program)
            mol = Molecule(
                program_id=int(program.id),
                primary_id="M-1",
                title="Mol1",
                created_at=datetime(2026, 2, 26),
                updated_at=datetime(2026, 2, 26),
            )
            db.add(mol)
            db.commit()
            db.refresh(mol)
            batch = Batch(
                molecule_id=int(mol.id),
                batch_id="B-1",
                title="Batch 1",
                created_at=datetime(2026, 2, 26, 0, 30, 0),
                updated_at=datetime(2026, 2, 26, 0, 30, 0),
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
            rec = DataRecord(
                program_id=int(program.id),
                molecule_id=int(mol.id),
                batch_id=int(batch.id),
                domain="in_vitro",
                data_type="binding",
                method="spr",
                title="SPR run",
                notes="",
                run_date="2026-02-26",
                created_at=datetime(2026, 2, 26, 0, 45, 0),
                updated_at=datetime(2026, 2, 26, 0, 45, 0),
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            db.execute(
                text(
                    """
                    INSERT INTO data_measurements
                    (data_record_id, metric_key, name, value_num, unit, qc_flag, ignore_for_model, created_at)
                    VALUES
                    (:rid, 'ec50', 'ec50', 12.0, 'nM', 'approved', 0, '2026-02-26T00:45:00'),
                    (:rid, 'kd', 'kd', 3.0, 'nM', 'approved', 0, '2026-02-26T00:45:01')
                    """
                ),
                {"rid": int(rec.id)},
            )
            db.commit()
            db.add(
                DecisionSnapshot(
                    program_id=int(program.id),
                    molecule_id=int(mol.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="vX",
                    engine_key="di",
                    schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps(
                        {
                            "decision_state": "ready",
                            "readiness": {"state": "ready"},
                            "gates": [],
                            "used_by_metric": {"ec50": [1001], "kd": [1002]},
                        }
                    ),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 1, 0, 0),
                )
            )
            db.commit()

            run = generate_molecule_report_v0(
                db,
                molecule_id=int(mol.id),
                as_of=datetime(2026, 2, 26, 2, 0, 0),
                policy_pins={"report_policy": "v0"},
            )
            payload = load_report_run_payload(run)
            sections = payload.get("sections", {})
            repro = sections.get("reproducibility_appendix") if isinstance(sections.get("reproducibility_appendix"), dict) else {}
            assert repro.get("measurement_keys") == ["ec50", "kd"]

            narrative = render_molecule_narrative(payload)
            measurements_row = next((x for x in narrative.get("evidence_status", []) if x.get("label") == "Measurements"), {})
            assert str(measurements_row.get("value") or "") == "ec50, kd"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_program_narrative_headline_uses_program_id_from_sections_metadata() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            program = Program(name="Program A", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(program)
            db.commit()
            db.refresh(program)
            mol = Molecule(
                program_id=int(program.id),
                primary_id="M-1",
                title="Mol1",
                created_at=datetime(2026, 2, 26),
                updated_at=datetime(2026, 2, 26),
            )
            db.add(mol)
            db.commit()
            db.refresh(mol)
            db.add(
                DecisionSnapshot(
                    program_id=int(program.id),
                    molecule_id=int(mol.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="vX",
                    engine_key="di",
                    schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps({"decision_state": "ready", "readiness": {"state": "ready"}, "gates": []}),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 1, 0, 0),
                )
            )
            db.commit()

            run = generate_program_report_v0(
                db,
                program_id=int(program.id),
                as_of=datetime(2026, 2, 26, 2, 0, 0),
                policy_pins={"report_policy": "v0"},
            )
            payload = load_report_run_payload(run)
            narrative = render_program_narrative(payload)
            assert "unidentified program" not in str(narrative.get("headline") or "").lower()
            assert f"program_id={int(program.id)}" in str(narrative.get("headline") or "")
        finally:
            db.close()
    finally:
        eng.dispose()


def test_program_report_molecule_rows_include_high_severity_risk_present() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            program = Program(name="P-risk", description="", created_at=datetime(2026, 2, 26), updated_at=datetime(2026, 2, 26))
            db.add(program)
            db.commit()
            db.refresh(program)
            mol = Molecule(
                program_id=int(program.id),
                primary_id="M-risk",
                title="Mol risk",
                created_at=datetime(2026, 2, 26),
                updated_at=datetime(2026, 2, 26),
            )
            db.add(mol)
            db.commit()
            db.refresh(mol)
            db.add(
                DecisionSnapshot(
                    program_id=int(program.id),
                    molecule_id=int(mol.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="vX",
                    engine_key="di",
                    schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps(
                        {
                            "decision_state": "ready",
                            "readiness": {"state": "ready"},
                            "gates": [],
                            "risk_flags_enriched": [{"severity": "high", "key": "agg"}],
                        }
                    ),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 2, 26, 1, 0, 0),
                )
            )
            db.commit()

            run = generate_program_report_v0(
                db,
                program_id=int(program.id),
                as_of=datetime(2026, 2, 26, 2, 0, 0),
                policy_pins={"report_policy": "v0"},
            )
            payload = load_report_run_payload(run)
            rows = payload.get("sections", {}).get("molecule_overview_table", {}).get("rows", [])
            assert len(rows) == 1
            assert bool(rows[0].get("high_severity_risk_present")) is True
        finally:
            db.close()
    finally:
        eng.dispose()
