from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import MoleculeBuildSpec, build_molecule_draft
from psi.services.builder_ops import apply_kih_hole, apply_kih_knob, remove_kih


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_kih_knob_hole_remove_ops() -> None:
    seq = "ABCDEFGHIJKLMNOP"
    knob, e1 = apply_kih_knob(sequence=seq)
    hole, e2 = apply_kih_hole(sequence=seq)
    rmv, e3 = remove_kih(sequence=knob)
    assert e1 == []
    assert e2 == []
    assert e3 == []
    assert knob[4] == "W"
    assert hole[4] == "T"
    assert rmv[4] == "A"


def test_builder_kih_toggle_draft_valid() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="KIH-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="KIH-PARENT",
                components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"},
            )
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="kih_toggle",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="KIH-CHILD",
                    operations=[{"type": "kih_toggle", "action": "apply_knob"}],
                ),
            )
            assert draft.is_valid is True
            assert draft.components["HC1"][4] == "W"
        finally:
            db.close()
    finally:
        eng.dispose()
