from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, DecisionSnapshot, Molecule, Program
from psi.core.utils import stable_json_dumps
from psi.services.data_records import apply_bulk_qc_action_for_record, create_data_record
from psi.services.evidence_preview import build_pending_evidence_preview_for_molecule, build_record_evidence_preview


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_record_evidence_preview_new_vs_existing_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 3, 0, 0, 0)
            p = Program(name="P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-1", title="Mol", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-1", title="Batch", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            rec = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Binding",
                results_json={"ec50": 1.2, "kd": 2.4},
            )

            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                decision_key="advance_to_in_vivo",
                rules_version="di.v0",
                engine_key="di",
                schema_version="di.snapshot.v0_1",
                inputs_json=stable_json_dumps({"engine_key": "di"}),
                outputs_json=stable_json_dumps({"decision_state": "ready", "gates": [], "used_by_metric": {"ec50": [{"measurement_id": 1001}]}}),
                evidence_ids_json="[]",
                created_at=now,
            )
            db.add(snap)
            db.commit()

            p1 = build_record_evidence_preview(db, record_id=int(rec.id))
            p2 = build_record_evidence_preview(db, record_id=int(rec.id))
            assert p1 == p2
            assert int(p1["counts"]["total_metrics"]) == 2
            assert int(p1["counts"]["already_present"]) == 1
            assert int(p1["counts"]["new_vs_last_snapshot"]) == 1
            by_key = {str(r["metric_key"]): str(r["status_key"]) for r in p1["rows"]}
            assert by_key["ec50"] == "already_present"
            assert by_key["kd"] == "new_vs_last_snapshot"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_pending_evidence_preview_for_molecule_filters_approved_entries() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 3, 0, 0, 0)
            p = Program(name="P2", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-2", title="Mol2", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-2", title="Batch2", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            rec_pending = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Pending rec",
                results_json={"ec50": 1.0},
            )
            rec_approved = create_data_record(
                db,
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Approved rec",
                results_json={"kd": 3.0},
            )
            apply_bulk_qc_action_for_record(db, record_id=int(rec_approved.id), action="approve", actor="scientist")

            rows = build_pending_evidence_preview_for_molecule(db, molecule_id=int(m.id))
            ids = [int(r["record_id"]) for r in rows]
            assert int(rec_pending.id) in ids
            assert int(rec_approved.id) not in ids
        finally:
            db.close()
    finally:
        eng.dispose()
