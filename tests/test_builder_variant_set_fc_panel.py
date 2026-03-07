from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import VariantSetBuildSpec, build_variant_set_draft
from psi.services.builder_ops import build_fc_panel_members


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_fc_panel_members_default_and_order() -> None:
    members = build_fc_panel_members(presets_text="")
    assert [m["member_label"] for m in members] == ["human_igg1", "mouse_igg2a", "fab_no_fc"]


def test_build_variant_set_fc_panel_draft_valid() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-FC", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="FC-PARENT",
                components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"},
            )
            members = build_fc_panel_members(presets_text="mouse_igg2a human_igg1")
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="fc_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="Fc panel",
                    naming_base="FCP",
                    members=members,
                ),
            )
            assert draft.is_valid is True
            assert [m.member_label for m in draft.members] == ["mouse_igg2a", "human_igg1"]
            assert all(m.molecule_spec.mode == "fc_swap" for m in draft.members)
        finally:
            db.close()
    finally:
        eng.dispose()
