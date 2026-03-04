from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Batch, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.di.run_manifest import create_di_run_manifest, verify_di_run
from psi.services.report_engine import generate_molecule_report_v0, generate_program_report_v0, load_report_run_payload
from psi.services.reports_v3 import get_v3_report_policy_pins


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_verify_di_run_happy_path() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P-verify", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.flush()
            m = Molecule(program_id=int(p.id), primary_id="M-verify", title="MV", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(m)
            db.flush()
            b = Batch(molecule_id=int(m.id), batch_id="B-verify", title="BV", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(b)
            db.flush()
            s0 = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v0",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps({"decision_state": "ready"}),
                evidence_ids_json="[]",
                created_at=datetime(2026, 3, 3, 1, 0, 0),
            )
            s1 = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                decision_key="advance_to_in_vivo",
                rules_version="v0",
                engine_key="di",
                schema_version="di.snapshot.v0_4",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps({"decision_state": "ready"}),
                evidence_ids_json="[]",
                created_at=datetime(2026, 3, 3, 1, 1, 0),
            )
            db.add_all([s0, s1])
            db.flush()
            run = create_di_run_manifest(
                db,
                run_id="verify-run-1",
                decision_key="advance_to_in_vivo",
                as_of="2026-03-03T00:00:00",
                policy_pins={},
                policy_semantics_hash=None,
                policy_package_hash=None,
                scope_root_id=int(m.id),
                program_id=int(p.id),
                subjects=[
                    {
                        "subject_index": 0,
                        "scope_type": "molecule",
                        "scope_id": int(m.id),
                        "molecule_id": int(m.id),
                        "decision_snapshot_id": int(s0.id),
                    },
                    {
                        "subject_index": 1,
                        "scope_type": "batch",
                        "scope_id": int(b.id),
                        "molecule_id": int(m.id),
                        "batch_id": int(b.id),
                        "decision_snapshot_id": int(s1.id),
                    },
                ],
            )
            db.commit()
            out = verify_di_run(db, di_run_id=int(run.id))
            assert out["ok"] is True
            assert out["errors"] == []
        finally:
            db.close()
    finally:
        eng.dispose()


def test_verify_di_run_detects_missing_snapshot_link() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P-verify-missing", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.flush()
            m = Molecule(program_id=int(p.id), primary_id="M-missing", title="MM", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(m)
            db.flush()
            run = create_di_run_manifest(
                db,
                run_id="verify-run-2",
                decision_key="advance_to_in_vivo",
                as_of="2026-03-03T00:00:00",
                policy_pins={},
                policy_semantics_hash=None,
                policy_package_hash=None,
                scope_root_id=int(m.id),
                program_id=int(p.id),
                subjects=[{"subject_index": 0, "scope_type": "molecule", "scope_id": int(m.id), "molecule_id": int(m.id)}],
            )
            db.commit()
            out = verify_di_run(db, di_run_id=int(run.id))
            assert out["ok"] is False
            assert any("missing_snapshot_link:index=0" in str(e) for e in out["errors"])
        finally:
            db.close()
    finally:
        eng.dispose()


def test_missing_policy_pins_warning_only_when_expected() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P-pins", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.flush()
            m = Molecule(program_id=int(p.id), primary_id="M-pins", title="MP", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(m)
            db.flush()
            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v0",
                    engine_key="di",
                    schema_version="di.snapshot.v0_4",
                    inputs_json=stable_json_dumps({"engine_key": "di"}),
                    outputs_json=stable_json_dumps({"decision_state": "ready", "readiness": {"state": "ready"}}),
                    evidence_ids_json="[]",
                    created_at=datetime(2026, 3, 3, 1, 0, 0),
                )
            )
            db.commit()

            full_row = generate_program_report_v0(
                db,
                program_id=int(p.id),
                as_of=datetime(2026, 3, 3, 2, 0, 0),
                policy_pins=get_v3_report_policy_pins("program_report"),
            )
            full_payload = load_report_run_payload(full_row)
            full_flags = (
                full_payload.get("sections", {})
                .get("reproducibility_appendix", {})
                .get("governance_red_flags", [])
            )
            full_codes = sorted(str(x.get("flag_code") or "") for x in full_flags if isinstance(x, dict))
            assert "missing_policy_pins_or_hashes" not in full_codes

            missing_row = generate_program_report_v0(
                db,
                program_id=int(p.id),
                as_of=datetime(2026, 3, 3, 2, 0, 0),
                policy_pins={},
            )
            missing_payload = load_report_run_payload(missing_row)
            missing_flags = (
                missing_payload.get("sections", {})
                .get("reproducibility_appendix", {})
                .get("governance_red_flags", [])
            )
            missing_codes = sorted(str(x.get("flag_code") or "") for x in missing_flags if isinstance(x, dict))
            assert "missing_policy_pins_or_hashes" in missing_codes
        finally:
            db.close()
    finally:
        eng.dispose()
