from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, ExperimentTask, Molecule, Program
from psi.services import molecules as molecule_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_molecule_detail_includes_open_experiment_tasks() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-mol-task", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-VIS", title="molecule", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            db.add_all(
                [
                    ExperimentTask(
                        program_id=int(p.id),
                        molecule_id=int(m.id),
                        metric_key="kd_nM",
                        suggested_assay="SPR",
                        status="planned",
                        urgency="high",
                        created_at=now,
                        updated_at=now,
                    ),
                    ExperimentTask(
                        program_id=int(p.id),
                        molecule_id=int(m.id),
                        metric_key="tm_c",
                        suggested_assay="DSF",
                        status="done",
                        urgency="low",
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            db.commit()

            ctx = molecule_svc.get_molecule_detail(db, int(m.id))
            rows = list(ctx.get("open_experiment_tasks") or [])
            assert len(rows) == 1
            assert str(rows[0]["metric_key"]) == "kd_nM"
            assert str(rows[0]["status"]) == "planned"
        finally:
            db.close()
    finally:
        eng.dispose()
