from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_experiment_task_schema_columns_and_indexes_exist() -> None:
    eng, _ = _mkdb()
    try:
        with eng.connect() as conn:
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(program_experiment_tasks)").fetchall()}
            assert {"program_id", "molecule_id", "status", "source_snapshot_id", "linked_data_record_id"} <= cols
            index_names = {row[1] for row in conn.exec_driver_sql("PRAGMA index_list(program_experiment_tasks)").fetchall()}
            assert "ix_experiment_tasks_program_status" in index_names
            assert "ix_experiment_tasks_molecule_status" in index_names
            assert "ix_experiment_tasks_program_molecule" in index_names
    finally:
        eng.dispose()


def test_experiment_task_model_supports_nullable_snapshot_and_data_record_links() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-model", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)

            m = Molecule(program_id=int(p.id), primary_id="M-ET-1", title="tasked", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            snap = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json="{}",
                evidence_ids_json="[]",
                is_superseded=0,
                created_at=now,
            )
            rec = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                domain="BIO",
                data_type="Binding",
                method="SPR",
                title="KD result",
                run_date="2026-03-07",
                created_at=now,
                updated_at=now,
            )
            db.add_all([snap, rec])
            db.commit()
            db.refresh(snap)
            db.refresh(rec)

            t = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
                status="planned",
                source_kind="board",
                notes="Confirm binding against panel A.",
                created_at=now,
                updated_at=now,
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            assert t.source_snapshot_id is None
            assert t.linked_data_record_id is None

            t.source_snapshot_id = int(snap.id)
            t.linked_data_record_id = int(rec.id)
            db.add(t)
            db.commit()
            db.refresh(t)

            assert int(t.program_id) == int(p.id)
            assert int(t.molecule_id) == int(m.id)
            assert int(t.source_snapshot_id) == int(snap.id)
            assert int(t.linked_data_record_id) == int(rec.id)
        finally:
            db.close()
    finally:
        eng.dispose()
