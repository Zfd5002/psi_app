from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import VariantSetBuildSpec, build_variant_set_draft
from psi.services.builder_ops import build_mutation_panel_members


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_mutation_panel_members_includes_singles_and_pairs() -> None:
    members = build_mutation_panel_members(
        mutation_tokens_text="N4Q M2L",
        include_pair_combinations=True,
        explicit_combos_text="",
    )
    assert [m["member_label"] for m in members] == ["N4Q", "M2L", "N4Q+M2L"]


def test_build_variant_set_mutation_panel_names_match_contract() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VSM-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="M-104",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            members = build_mutation_panel_members(
                mutation_tokens_text="N4Q G3L",
                include_pair_combinations=True,
                explicit_combos_text="",
            )
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="mutation_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="Cleanup panel",
                    naming_base="M-104",
                    members=members,
                ),
            )
            assert draft.is_valid is True
            assert [m.molecule_spec.new_primary_id for m in draft.members] == [
                "M_104_N4Q",
                "M_104_G3L",
                "M_104_N4Q_G3L",
            ]
        finally:
            db.close()
    finally:
        eng.dispose()
