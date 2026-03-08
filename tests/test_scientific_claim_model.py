from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import (
    Base,
    DataRecord,
    DecisionSnapshot,
    ExperimentTask,
    Molecule,
    Program,
    ScientificClaim,
    ScientificClaimDecisionLink,
    ScientificClaimEvidenceLink,
    ScientificClaimTaskLink,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_scientific_claim_tables_and_columns_exist() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            tables = {r[0] for r in db.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
            assert "scientific_claims" in tables
            assert "scientific_claim_evidence_links" in tables
            assert "scientific_claim_decision_links" in tables
            assert "scientific_claim_task_links" in tables
            cols = {r[1] for r in db.execute(text("PRAGMA table_info(scientific_claims)"))}
            assert {"scope_type", "claim_type", "statement", "status", "confidence_level"} <= cols
        finally:
            db.close()
    finally:
        eng.dispose()


def test_scientific_claim_lifecycle_and_links_are_additive() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-claim-model", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-claim-model", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            rec = DataRecord(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, domain="Biological", data_type="Binding", method="BLI", title="r", created_at=now, updated_at=now)
            task = ExperimentTask(program_id=int(p.id), molecule_id=int(m.id), status="planned", created_at=now, updated_at=now)
            snap = DecisionSnapshot(program_id=int(p.id), molecule_id=int(m.id), batch_id=None, decision_key="advance_to_in_vivo", rules_version="v1", inputs_json="{}", outputs_json="{}", evidence_ids_json="[]", is_superseded=0, created_at=now)
            db.add_all([rec, task, snap]); db.commit(); db.refresh(rec); db.refresh(task); db.refresh(snap)

            c = ScientificClaim(
                scope_type="molecule",
                molecule_id=int(m.id),
                program_id=int(p.id),
                title="Affinity supports advancement",
                claim_type="affinity",
                statement="Molecule has high-affinity target binding.",
                status="hypothesis",
                confidence_level="low",
                rationale="initial assay plan",
                created_at=now,
                updated_at=now,
            )
            db.add(c); db.commit(); db.refresh(c)
            db.add_all(
                [
                    ScientificClaimEvidenceLink(claim_id=int(c.id), data_record_id=int(rec.id), direction="contextual", created_at=now),
                    ScientificClaimDecisionLink(claim_id=int(c.id), decision_snapshot_id=int(snap.id), relationship_type="informs", created_at=now),
                    ScientificClaimTaskLink(claim_id=int(c.id), experiment_task_id=int(task.id), relationship_type="tests", created_at=now),
                ]
            )
            db.commit()
            assert int(db.query(ScientificClaim).count()) == 1
            assert int(db.query(ScientificClaimEvidenceLink).count()) == 1
            assert int(db.query(ScientificClaimDecisionLink).count()) == 1
            assert int(db.query(ScientificClaimTaskLink).count()) == 1
        finally:
            db.close()
    finally:
        eng.dispose()
