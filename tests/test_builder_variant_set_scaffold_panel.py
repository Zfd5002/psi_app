from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import VariantSetBuildSpec, build_variant_set_draft
from psi.services.builder_ops import build_scaffold_panel_members


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_scaffold_panel_members_defaults() -> None:
    members = build_scaffold_panel_members(
        scaffold_presets_text="",
        light_chain_type="kappa",
        numbering_scheme="kabat",
        cdrs={"HCDR1": "AA", "HCDR2": "BB", "HCDR3": "CC", "LCDR1": "DD", "LCDR2": "EE", "LCDR3": "FF"},
    )
    assert [m["member_label"] for m in members] == ["human_vh3_vk1", "human_vh1_vk1"]


def test_build_variant_set_scaffold_panel_marks_reconstructed_flows() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-SC", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="SC-PARENT",
                components={"HC1": "AAAAAAAAAA", "LC1": "BBBBBBBBBB"},
            )
            members = build_scaffold_panel_members(
                scaffold_presets_text="human_vh1_vk1 human_vh3_vk1",
                light_chain_type="kappa",
                numbering_scheme="kabat",
                cdrs={"HCDR1": "AA", "HCDR2": "BB", "HCDR3": "CC", "LCDR1": "DD", "LCDR2": "EE", "LCDR3": "FF"},
            )
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="scaffold_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="Scaffold panel",
                    naming_base="SCF",
                    members=members,
                ),
            )
            assert draft.is_valid is True
            assert [m.member_label for m in draft.members] == ["human_vh1_vk1", "human_vh3_vk1"]
            assert all("reconstructed_from_cdrs" in m.member_summary for m in draft.members)
            assert all(m.molecule_spec.mode == "cdr_graft" for m in draft.members)
        finally:
            db.close()
    finally:
        eng.dispose()
