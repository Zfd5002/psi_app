from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, Molecule, Program
from psi.services import claims as claims_svc
from psi.services import programs as program_svc


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_program_detail_includes_claim_summary_and_preview() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-pcs", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-pcs", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            claims_svc.create_claim(db, scope_type="molecule", molecule_id=int(m.id), program_id=int(p.id), title="C1", claim_type="affinity", statement="x", status="emerging")
            claims_svc.create_claim(db, scope_type="program", molecule_id=None, program_id=int(p.id), title="C2", claim_type="in_vivo_readiness", statement="x", status="supported")
            old_sql = program_svc.PROGRAM_EVIDENCE_ROWS_SQL
            program_svc.PROGRAM_EVIDENCE_ROWS_SQL = """
            SELECT
              dr.molecule_id AS molecule_id,
              dm.name AS metric_key
            FROM data_records dr
            JOIN data_measurements dm ON dm.data_record_id = dr.id
            WHERE dr.program_id = :pid
              AND dr.molecule_id IS NOT NULL
            ORDER BY dr.molecule_id ASC, dm.name ASC, dm.id ASC
            """
            ctx = program_svc.get_program_detail(db, int(p.id))
            program_svc.PROGRAM_EVIDENCE_ROWS_SQL = old_sql
            assert "program_claim_summary" in ctx
            assert "program_claims_preview" in ctx
            assert int(ctx["program_claim_summary"]["hypothesis_or_emerging"]) >= 1
            assert int(ctx["program_claim_summary"]["supported"]) >= 1
            assert len(ctx["program_claims_preview"]) >= 2
        finally:
            db.close()
    finally:
        eng.dispose()
