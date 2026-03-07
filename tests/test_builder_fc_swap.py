from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import MoleculeBuildSpec, build_molecule_draft
from psi.services.builder_ops import apply_fc_swap


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_apply_fc_swap_requires_hc1() -> None:
    out, errors = apply_fc_swap(components={"LC1": "BBBB"}, preset="human_igg1")
    assert out["LC1"] == "BBBB"
    assert "Heavy chain HC1 is required for Fc swap." in errors


def test_apply_fc_swap_human_igg1_changes_hc_tail() -> None:
    out, errors = apply_fc_swap(components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"}, preset="human_igg1")
    assert errors == []
    assert out["HC1"].endswith("ASTKGPSVFP")


def test_builder_fc_swap_draft_valid_with_supported_preset() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="FC-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="FC-PARENT",
                components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"},
            )
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="fc_swap",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="FC-CHILD",
                    operations=[{"type": "fc_swap", "preset": "human_igg1"}],
                ),
            )
            assert draft.is_valid is True
            assert draft.components["HC1"].endswith("ASTKGPSVFP")
        finally:
            db.close()
    finally:
        eng.dispose()
