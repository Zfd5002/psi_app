from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import VariantSetBuildSpec, build_variant_set_draft
from psi.services.builder_ops import build_kih_panel_members


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_kih_panel_members_default() -> None:
    members = build_kih_panel_members(kih_presets_text="")
    assert [m["member_label"] for m in members] == ["off", "on_knob"]


def test_build_variant_set_kih_panel_draft_valid() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-KIH", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="KIH-PARENT",
                components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"},
            )
            members = build_kih_panel_members(kih_presets_text="off on_hole")
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="kih_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="KIH panel",
                    naming_base="KIH",
                    members=members,
                ),
            )
            assert draft.is_valid is True
            assert [m.member_label for m in draft.members] == ["off", "on_hole"]
            assert [m.molecule_spec.mode for m in draft.members] == ["kih_toggle", "kih_toggle"]
        finally:
            db.close()
    finally:
        eng.dispose()
