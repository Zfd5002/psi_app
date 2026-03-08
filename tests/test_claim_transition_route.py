from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import claims as claims_svc
from psi.web.routers import claims as claims_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_transition_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in claims_router.router.routes}
    assert ("/claims/{claim_id}/transition", ("POST",)) in route_keys


def test_claim_transition_route_applies_valid_transition() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-claim-tr", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claim-tr", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Claim",
                claim_type="affinity",
                statement="test",
            )
            resp = claims_router.claim_transition(
                claim_id=int(c.id),
                request=None,
                status="emerging",
                redirect_to="",
                db=db,
            )
            assert int(getattr(resp, "status_code", 0)) == 303
            row = claims_svc.get_claim(db, claim_id=int(c.id))
            assert row is not None
            assert str(row.status) == "emerging"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claim_transition_route_rejects_invalid_transition() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-claim-tr-bad", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claim-tr-bad", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            c = claims_svc.create_claim(
                db,
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Claim",
                claim_type="affinity",
                statement="test",
            )
            with pytest.raises(HTTPException) as exc:
                claims_router.claim_transition(
                    claim_id=int(c.id),
                    request=None,
                    status="supported",
                    redirect_to="",
                    db=db,
                )
            assert int(exc.value.status_code) == 400
            row = claims_svc.get_claim(db, claim_id=int(c.id))
            assert row is not None
            assert str(row.status) == "hypothesis"
        finally:
            db.close()
    finally:
        eng.dispose()
