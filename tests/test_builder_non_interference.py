from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import (
    Base,
    Batch,
    DecisionSnapshot,
    Program,
    ProgramMembership,
    ReportRun,
)
from psi.services import molecules as molecule_svc
from psi.services.builder import (
    MoleculeBuildSpec,
    MoleculeCreateMeta,
    build_molecule_draft,
    create_molecule_from_draft,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_builder_create_has_no_program_di_batch_report_side_effects() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Builder-Isolation", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)

            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="ISO-PARENT",
                title="Iso Parent",
                components={"HC1": "AAAA", "LC1": "BBBB"},
            )

            before = {
                "memberships": int(db.query(ProgramMembership).count()),
                "snapshots": int(db.query(DecisionSnapshot).count()),
                "batches": int(db.query(Batch).count()),
                "reports": int(db.query(ReportRun).count()),
            }

            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="clone",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="ISO-CHILD",
                    new_title="Iso Child",
                    rationale="non-interference check",
                ),
            )
            assert draft.is_valid is True
            child = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="tester", note="non-interference"))
            assert int(child.program_id) == int(parent.program_id)

            after = {
                "memberships": int(db.query(ProgramMembership).count()),
                "snapshots": int(db.query(DecisionSnapshot).count()),
                "batches": int(db.query(Batch).count()),
                "reports": int(db.query(ReportRun).count()),
            }
            assert after == before
        finally:
            db.close()
    finally:
        eng.dispose()
