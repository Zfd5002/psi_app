from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import MoleculeBuildSpec, build_molecule_draft
from psi.services.builder_ops import apply_cdr_graft


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_apply_cdr_graft_validates_numbering_and_builds_components() -> None:
    comps, errors = apply_cdr_graft(
        framework_preset="human_vh3_vk1",
        light_chain_type="kappa",
        numbering_scheme="kabat",
        cdrs={
            "HCDR1": "AAAA",
            "HCDR2": "BBBB",
            "HCDR3": "CCCC",
            "LCDR1": "DDDD",
            "LCDR2": "EEEE",
            "LCDR3": "FFFF",
        },
    )
    assert errors == []
    assert "HC1" in comps and "LC1" in comps


def test_builder_cdr_graft_draft_valid() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="CDR-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="CDR-PARENT",
                components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"},
            )
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="cdr_graft",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="CDR-CHILD",
                    operations=[
                        {
                            "type": "cdr_graft",
                            "framework_preset": "human_vh3_vk1",
                            "light_chain_type": "kappa",
                            "numbering_scheme": "kabat",
                            "HCDR1": "AAAA",
                            "HCDR2": "BBBB",
                            "HCDR3": "CCCC",
                            "LCDR1": "DDDD",
                            "LCDR2": "EEEE",
                            "LCDR3": "FFFF",
                        }
                    ],
                ),
            )
            assert draft.is_valid is True
            assert draft.components["HC1"]
            assert draft.components["LC1"]
            assert "framework_preset=human_vh3_vk1" in draft.assumptions
            assert len(draft.changed_residues) >= 1
        finally:
            db.close()
    finally:
        eng.dispose()
