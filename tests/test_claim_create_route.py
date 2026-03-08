from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program, ScientificClaim
from psi.web.routers import claims as claims_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_claim_create_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in claims_router.router.routes}
    assert ("/claims/new", ("GET",)) in route_keys
    assert ("/claims/new", ("POST",)) in route_keys


def test_claim_create_route_creates_molecule_scoped_claim() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-claim-new", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claim-new", title="", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            resp = claims_router.claim_create(
                request=None,
                molecule_id=int(m.id),
                title="Affinity claim",
                claim_type="affinity",
                description="Expected high-affinity binding profile",
                db=db,
            )
            assert int(getattr(resp, "status_code", 0)) == 303
            rows = db.query(ScientificClaim).order_by(ScientificClaim.id.asc()).all()
            assert len(rows) == 1
            row = rows[0]
            assert int(row.molecule_id) == int(m.id)
            assert int(row.program_id) == int(p.id)
            assert str(row.title) == "Affinity claim"
            assert str(row.claim_type) == "affinity"
            assert str(row.statement).startswith("Expected high-affinity")
        finally:
            db.close()
    finally:
        eng.dispose()
