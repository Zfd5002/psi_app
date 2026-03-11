from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, MoleculeComponent, Program
from psi.services import builder as builder_svc
from psi.web.routers import molecules as molecules_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


class _DummyRequest:
    def __init__(self, form_data: dict[str, object]):
        self.app = SimpleNamespace(state=SimpleNamespace())
        self._form_data = dict(form_data)

    async def form(self):
        return dict(self._form_data)


def test_extract_components_from_form_accepts_uppercase_and_lowercase_keys() -> None:
    upper = molecules_router._extract_components_from_form(
        {
            "HC1": "  MSGN  ",
            "LC1": "BBBB",
            "HC2": "",
            "LC2": "  ",
        }
    )
    assert upper == {"HC1": "MSGN", "LC1": "BBBB", "HC2": "", "LC2": ""}

    lower = molecules_router._extract_components_from_form(
        {
            "hc1": "MSGN",
            "lc1": "BBBB",
            "hc2": "",
            "lc2": "",
        }
    )
    assert lower == {"HC1": "MSGN", "LC1": "BBBB", "HC2": "", "LC2": ""}


def test_create_molecule_route_persists_uppercase_structured_components_for_builder_parent() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="Structured Parent Program", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)

            req = _DummyRequest(
                {
                    "program_id": str(int(p.id)),
                    "primary_id": "TUT1-A",
                    "title": "Tutorial Parent",
                    "description": "",
                    "description_user": "Synthetic tutorial parent",
                    "sequences": "",
                    "molecule_format": "IgG",
                    "heavy_compute_enabled": "0",
                    "fasta_bundle": "",
                    "HC1": "MSGN",
                    "LC1": "BBBB",
                }
            )

            resp = asyncio.run(molecules_router.create_molecule(req, BackgroundTasks(), db))
            assert int(resp.status_code) == 303
            location = str(resp.headers.get("location") or "")
            assert location.startswith("/molecules/")
            molecule_id = int(location.rsplit("/", 1)[-1])

            rows = (
                db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(molecule_id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            )
            role_to_seq = {str(r.role): str(r.fasta or "") for r in rows}
            assert role_to_seq["HC1"] == "MSGN"
            assert role_to_seq["LC1"] == "BBBB"

            draft = builder_svc.build_molecule_draft(
                db,
                builder_svc.MoleculeBuildSpec(
                    mode="point_mutation",
                    parent_molecule_id=int(molecule_id),
                    new_primary_id="TUT1-A1",
                    operations=[{"type": "point_mutation", "component": "HC1", "mutations": "S2A"}],
                ),
            )
            assert bool(draft.is_valid) is True
            assert "Parent molecule has no structured components to derive from." not in list(draft.errors or [])
        finally:
            db.close()
    finally:
        eng.dispose()
