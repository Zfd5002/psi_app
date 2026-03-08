from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DataRecord, Evidence, EvidenceCitation, ExperimentTask, Molecule, Program
from psi.services import workflow_center as svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_program_workflow_center_rolls_up_recent_learning() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-wfc", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-WFC", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            t1 = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                status="planned",
                source_kind="board",
                metric_key="kd_nM",
                created_at=now,
                updated_at=now,
            )
            t2 = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                status="in_progress",
                source_kind="plan",
                metric_key="ec50_nM",
                created_at=now,
                updated_at=now,
            )
            db.add_all([t1, t2])
            db.commit()

            r1 = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                title="R1",
                domain="Biological",
                data_type="Binding",
                method="BLI",
                created_at=now,
                updated_at=now,
            )
            r2 = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                title="R2",
                domain="Biological",
                data_type="Binding",
                method="SPR",
                created_at=now,
                updated_at=now,
            )
            db.add_all([r1, r2])
            db.commit()
            db.refresh(r1)
            db.refresh(r2)

            ev = Evidence(
                program_id=int(p.id),
                molecule_id=int(m.id),
                domain="Biological",
                evidence_type="binding_support",
                strength=3,
                summary="S",
                created_at=now,
                updated_at=now,
            )
            db.add(ev)
            db.commit()
            db.refresh(ev)
            db.add(EvidenceCitation(evidence_id=int(ev.id), data_record_id=int(r1.id)))
            db.commit()

            out = svc.build_program_workflow_center(db, program_id=int(p.id))
            assert len(out["ready_to_start"]) == 1
            assert len(out["in_progress"]) == 1
            assert len(out["recent_data_records"]) >= 2
            assert len(out["recent_evidence"]) >= 1
            pending_ids = {int(x.id) for x in out["pending_interpretation"]}
            assert int(r2.id) in pending_ids
            assert int(r1.id) not in pending_ids
        finally:
            db.close()
    finally:
        eng.dispose()

