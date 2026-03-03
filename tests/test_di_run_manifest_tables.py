from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Program
from psi.services.di.run_manifest import create_di_run_manifest, list_run_subjects, lookup_run_by_run_id


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_di_run_tables_exist_and_roundtrip_minimal_insert() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            p = Program(name="P", created_at=datetime(2026, 3, 3), updated_at=datetime(2026, 3, 3))
            db.add(p)
            db.flush()

            run = create_di_run_manifest(
                db,
                run_id="run-001",
                decision_key="advance_to_in_vivo",
                as_of="2026-03-03T00:00:00",
                policy_pins={"comparability_policy": {"policy_version": "v0.2"}},
                policy_semantics_hash="abc",
                policy_package_hash="def",
                scope_root_id=11,
                program_id=int(p.id),
                subjects=[
                    {"subject_index": 0, "scope_type": "molecule", "scope_id": 11, "molecule_id": 11},
                    {"subject_index": 1, "scope_type": "batch", "scope_id": 21, "molecule_id": 11, "batch_id": 21},
                ],
            )
            db.commit()

            got = lookup_run_by_run_id(db, run_id="run-001")
            assert got is not None
            assert int(got.id) == int(run.id)
            rows = list_run_subjects(db, di_run_id=int(run.id))
            assert [int(r.subject_index) for r in rows] == [0, 1]
            assert [str(r.scope_type) for r in rows] == ["molecule", "batch"]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_di_run_subject_unique_index_and_ordering() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            create_di_run_manifest(
                db,
                run_id="run-dup",
                decision_key="advance_to_in_vivo",
                as_of="2026-03-03T00:00:00",
                policy_pins={},
                policy_semantics_hash=None,
                policy_package_hash=None,
                scope_root_id=100,
                program_id=None,
                subjects=[
                    {"subject_index": 2, "scope_type": "batch", "scope_id": 202, "batch_id": 202},
                    {"subject_index": 0, "scope_type": "molecule", "scope_id": 100, "molecule_id": 100},
                    {"subject_index": 1, "scope_type": "batch", "scope_id": 201, "batch_id": 201},
                ],
            )
            db.commit()

            run = lookup_run_by_run_id(db, run_id="run-dup")
            assert run is not None
            ordered = list_run_subjects(db, di_run_id=int(run.id))
            assert [int(x.subject_index) for x in ordered] == [0, 1, 2]

            with pytest.raises(IntegrityError):
                create_di_run_manifest(
                    db,
                    run_id="run-dup-2",
                    decision_key="advance_to_in_vivo",
                    as_of="2026-03-03T00:00:00",
                    policy_pins={},
                    policy_semantics_hash=None,
                    policy_package_hash=None,
                    scope_root_id=101,
                    program_id=None,
                    subjects=[
                        {"subject_index": 0, "scope_type": "molecule", "scope_id": 101, "molecule_id": 101},
                        {"subject_index": 0, "scope_type": "batch", "scope_id": 301, "batch_id": 301},
                    ],
                )
                db.flush()
        finally:
            db.close()
    finally:
        eng.dispose()
