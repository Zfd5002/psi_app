from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.report_engine import generate_molecule_report_v0, generate_program_report_v0, load_report_run_payload
from psi.services.v3_narrative import render_molecule_narrative, render_program_narrative


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_molecule_narrative_measurements_match_repro_appendix_keys() -> None:
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
            repro = payload.get("sections", {}).get("reproducibility_appendix", {})
            repro_keys = repro.get("measurement_keys") if isinstance(repro.get("measurement_keys"), list) else []
            assert repro_keys == ["ec50", "kd"]

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
