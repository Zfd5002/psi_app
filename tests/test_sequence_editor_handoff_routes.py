from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Program
from psi.services import molecules as molecule_svc
from psi.web.routers import builder as builder_router
from psi.web.ui_labels import humanize_state


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


class _DummyRequest:
    def __init__(self, form_data: dict[str, object]):
        templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"))
        templates.env.filters["humanize_state"] = humanize_state
        self.app = SimpleNamespace(state=SimpleNamespace(templates=templates))
        self._form_data = dict(form_data)

    async def form(self):
        return dict(self._form_data)


def test_sequence_editor_payload_reaches_builder_point_mutation_draft_route() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="SE-Handoff-PM", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="M-SE-1",
                title="Source",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )

            req = _DummyRequest(
                {
                    "parent_molecule_id": int(parent.id),
                    "new_primary_id": "M-SE-1_edit",
                    "new_title": "M-SE-1 edit",
                    "rationale": "sequence editor queued mutations",
                    "component": "HC1",
                    "mutations": "N4Q S2A",
                    "queue_origin": "sequence_editor",
                    "source_primary_id": "M-SE-1",
                    "queued_component": "HC1",
                    "queued_mutation_count": "2",
                    "queued_mutation_tokens": "N4Q S2A",
                }
            )
            response = asyncio.run(builder_router.builder_point_mutation_build_draft(req, db))
            form_data = response.context["form_data"]
            draft = response.context["draft"]
            assert form_data["queue_origin"] == "sequence_editor"
            assert form_data["source_primary_id"] == "M-SE-1"
            assert form_data["queued_component"] == "HC1"
            assert form_data["queued_mutation_count"] == 2
            assert form_data["mutations"] == "S2A N4Q"
            assert bool(draft.is_valid) is True
        finally:
            db.close()
    finally:
        eng.dispose()


def test_sequence_editor_payload_reaches_variant_set_draft_route() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="SE-Handoff-VS", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="M-SE-2",
                title="Source2",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )

            req = _DummyRequest(
                {
                    "parent_molecule_id": int(parent.id),
                    "family_type": "mutation_panel",
                    "set_name": "M-SE-2 sequence edit panel",
                    "naming_base": "M-SE-2",
                    "rationale": "sequence editor queued mutations",
                    "mutation_tokens": "N4Q S2A",
                    "queued_component": "HC1",
                    "include_pair_combinations": "0",
                    "explicit_combos": "N4Q+S2A",
                    "fc_presets": "",
                    "kih_presets": "",
                    "scaffold_presets": "",
                    "light_chain_type": "kappa",
                    "numbering_scheme": "kabat",
                    "HCDR1": "",
                    "HCDR2": "",
                    "HCDR3": "",
                    "LCDR1": "",
                    "LCDR2": "",
                    "LCDR3": "",
                }
            )
            response = asyncio.run(builder_router.builder_variant_set_build_draft(req, db))
            form_data = response.context["form_data"]
            draft = response.context["draft"]
            assert form_data["queued_component"] == "HC1"
            assert form_data["mutation_tokens"] == "S2A N4Q"
            assert bool(draft.is_valid) is True
            assert [m.member_label for m in draft.members] == ["S2A", "N4Q", "N4Q+S2A"]
        finally:
            db.close()
    finally:
        eng.dispose()
