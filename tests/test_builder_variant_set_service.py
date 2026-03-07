from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, BuilderVariantSet, BuilderVariantSetMember, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import (
    VariantSetBuildSpec,
    VariantSetCreateMeta,
    build_variant_set_draft,
    create_variant_set_from_draft,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_variant_set_draft_build_is_deterministic_ordered() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="VS-PARENT",
                title="VS Parent",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            spec = VariantSetBuildSpec(
                family_type="mutation_panel",
                parent_molecule_id=int(parent.id),
                set_name="SetA",
                naming_base="M104",
                members=[
                    {"sort_index": 2, "member_label": "M101L", "mode": "point_mutation", "operations": [{"type": "point_mutation", "component": "HC1", "mutations": "G3L"}]},
                    {"sort_index": 1, "member_label": "N54Q", "mode": "point_mutation", "operations": [{"type": "point_mutation", "component": "HC1", "mutations": "N4Q"}]},
                ],
            )
            d1 = build_variant_set_draft(db, spec)
            d2 = build_variant_set_draft(db, spec)
            assert d1.is_valid is True
            assert d2.is_valid is True
            assert [m.member_label for m in d1.members] == ["N54Q", "M101L"]
            assert [m.molecule_spec.new_primary_id for m in d1.members] == [m.molecule_spec.new_primary_id for m in d2.members]
        finally:
            db.close()
    finally:
        eng.dispose()


def test_variant_set_create_persists_set_and_members() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-P2", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="VS2-PARENT",
                title="VS2 Parent",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="mutation_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="SetB",
                    naming_base="M200",
                    members=[
                        {"sort_index": 1, "member_label": "N4Q", "mode": "point_mutation", "operations": [{"type": "point_mutation", "component": "HC1", "mutations": "N4Q"}]},
                    ],
                ),
            )
            assert draft.is_valid is True
            result = create_variant_set_from_draft(db, draft, VariantSetCreateMeta(actor="tester"))
            assert int(result.variant_set_id) > 0
            assert len(result.molecule_ids) == 1
            vset = db.get(BuilderVariantSet, int(result.variant_set_id))
            assert vset is not None
            assert str(vset.builder_mode) == "mutation_panel"
            members = (
                db.query(BuilderVariantSetMember)
                .filter(BuilderVariantSetMember.variant_set_id == int(result.variant_set_id))
                .order_by(BuilderVariantSetMember.sort_index.asc(), BuilderVariantSetMember.id.asc())
                .all()
            )
            assert len(members) == 1
            assert int(members[0].molecule_id) == int(result.molecule_ids[0])
        finally:
            db.close()
    finally:
        eng.dispose()
