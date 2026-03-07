from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, BuilderVariantSet, BuilderVariantSetMember, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import add_variant_set_members, create_variant_set_record


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_builder_variant_set_tables_persist_and_query() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            row = create_variant_set_record(
                db,
                name="Liability Cleanup",
                builder_mode="mutation_panel",
                summary="N54Q panel",
                rationale="cleanup risk",
                spec_json='{"mode":"mutation_panel"}',
            )
            assert int(row.id) > 0
            fetched = db.get(BuilderVariantSet, int(row.id))
            assert fetched is not None
            assert str(fetched.name) == "Liability Cleanup"
            assert str(fetched.builder_mode) == "mutation_panel"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_builder_variant_set_member_order_is_deterministic() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="BVS-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m1 = molecule_svc.create_molecule(db, program_id=int(p.id), primary_id="BVS-1", components={"HC1": "AAAA", "LC1": "BBBB"})
            m2 = molecule_svc.create_molecule(db, program_id=int(p.id), primary_id="BVS-2", components={"HC1": "AAAC", "LC1": "BBBB"})
            vset = create_variant_set_record(db, name="Set 1", builder_mode="mutation_panel")
            rows = add_variant_set_members(
                db,
                variant_set_id=int(vset.id),
                members=[
                    {"sort_index": 2, "molecule_id": int(m2.id), "member_label": "B"},
                    {"sort_index": 1, "molecule_id": int(m1.id), "member_label": "A"},
                ],
            )
            assert [int(r.sort_index) for r in rows] == [1, 2]
            assert [int(r.molecule_id) for r in rows] == [int(m1.id), int(m2.id)]
            fetched = (
                db.query(BuilderVariantSetMember)
                .filter(BuilderVariantSetMember.variant_set_id == int(vset.id))
                .order_by(BuilderVariantSetMember.sort_index.asc(), BuilderVariantSetMember.id.asc())
                .all()
            )
            assert [str(r.member_label) for r in fetched] == ["A", "B"]
        finally:
            db.close()
    finally:
        eng.dispose()
