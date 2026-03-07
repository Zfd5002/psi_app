from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.services.builder import MoleculeBuildSpec, build_molecule_draft


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_builder_recognizes_expanded_modes() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Builder-Modes", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="MODE-PARENT",
                components={"HC1": "ABCDEFGHIJKLMNOP", "LC1": "BBBB"},
            )
            for mode in ("cdr_graft", "fc_swap", "kih_toggle"):
                ops = []
                if mode == "fc_swap":
                    ops = [{"type": "fc_swap", "preset": "human_igg1"}]
                if mode == "kih_toggle":
                    ops = [{"type": "kih_toggle", "action": "apply_knob"}]
                if mode == "cdr_graft":
                    ops = [{
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
                    }]
                draft = build_molecule_draft(
                    db,
                    MoleculeBuildSpec(
                        mode=mode,
                        parent_molecule_id=int(parent.id),
                        new_primary_id=f"CHILD-{mode}",
                        new_title=f"Child {mode}",
                        operations=ops,
                    ),
                )
                assert draft.mode == mode
                assert draft.derivation_type == mode
                assert draft.is_valid is True
        finally:
            db.close()
    finally:
        eng.dispose()
