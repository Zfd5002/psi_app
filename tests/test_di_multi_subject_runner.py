from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, DIRunSubject, DecisionSnapshot, Molecule, Program
from psi.services.di.runner import run_di_multi_subject


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _policy_path() -> Path:
    return Path(__file__).resolve().parents[1] / "psi" / "core" / "di" / "policies" / "advance_to_in_vivo_v0_5.json"


def test_di_multi_subject_ordering_stable() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="ProgramMS", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.flush()
            m = Molecule(
                program_id=int(p.id),
                primary_id="M-MS",
                title="Multi Subject",
                created_at=datetime(2026, 3, 3),
                updated_at=datetime(2026, 3, 3),
            )
            db.add(m)
            db.flush()
            db.add_all(
                [
                    Batch(molecule_id=int(m.id), batch_id="B1", title="Old", created_at=datetime(2026, 2, 1), updated_at=datetime(2026, 2, 1)),
                    Batch(molecule_id=int(m.id), batch_id="B2", title="Mid", created_at=datetime(2026, 2, 2), updated_at=datetime(2026, 2, 2)),
                    Batch(molecule_id=int(m.id), batch_id="B3", title="New", created_at=datetime(2026, 2, 3), updated_at=datetime(2026, 2, 3)),
                ]
            )
            db.commit()

            run1 = run_di_multi_subject(
                db,
                molecule_id=int(m.id),
                decision_key="advance_to_in_vivo",
                as_of_ts="2026-03-03T00:00:00",
                policy_path=_policy_path(),
            )
            run2 = run_di_multi_subject(
                db,
                molecule_id=int(m.id),
                decision_key="advance_to_in_vivo",
                as_of_ts="2026-03-03T00:00:00",
                policy_path=_policy_path(),
            )

            rows1 = (
                db.query(DIRunSubject)
                .filter(DIRunSubject.di_run_id == int(run1["di_run_id"]))
                .order_by(DIRunSubject.subject_index.asc(), DIRunSubject.id.asc())
                .all()
            )
            rows2 = (
                db.query(DIRunSubject)
                .filter(DIRunSubject.di_run_id == int(run2["di_run_id"]))
                .order_by(DIRunSubject.subject_index.asc(), DIRunSubject.id.asc())
                .all()
            )
            assert [(r.scope_type, int(r.scope_id)) for r in rows1] == [(r.scope_type, int(r.scope_id)) for r in rows2]
            assert rows1[0].scope_type == "molecule"
            assert rows1[1].scope_type == "batch"
            assert [int(x.scope_id) for x in rows1[1:]] == sorted([int(x.scope_id) for x in rows1[1:]], reverse=True)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_di_multi_subject_links_snapshots_to_run_subjects() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="ProgramLink", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.flush()
            m = Molecule(
                program_id=int(p.id),
                primary_id="M-LINK",
                title="Links",
                created_at=datetime(2026, 3, 3),
                updated_at=datetime(2026, 3, 3),
            )
            db.add(m)
            db.flush()
            b = Batch(
                molecule_id=int(m.id),
                batch_id="B-LINK",
                title="Batch Link",
                created_at=datetime(2026, 2, 4),
                updated_at=datetime(2026, 2, 4),
            )
            db.add(b)
            db.commit()

            run = run_di_multi_subject(
                db,
                molecule_id=int(m.id),
                decision_key="advance_to_in_vivo",
                as_of_ts="2026-03-03T00:00:00",
                policy_path=_policy_path(),
            )
            rows = (
                db.query(DIRunSubject)
                .filter(DIRunSubject.di_run_id == int(run["di_run_id"]))
                .order_by(DIRunSubject.subject_index.asc(), DIRunSubject.id.asc())
                .all()
            )
            assert rows
            assert all(r.decision_snapshot_id is not None for r in rows)
            snaps = (
                db.query(DecisionSnapshot)
                .filter(DecisionSnapshot.id.in_([int(r.decision_snapshot_id) for r in rows if r.decision_snapshot_id is not None]))
                .order_by(DecisionSnapshot.id.asc())
                .all()
            )
            assert len(snaps) == len(rows)
        finally:
            db.close()
    finally:
        eng.dispose()
