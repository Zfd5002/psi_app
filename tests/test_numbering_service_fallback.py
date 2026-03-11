from __future__ import annotations

import json
from datetime import datetime

from psi.core.models import DomainArtifact, DomainInstance, Molecule, MoleculeComponent, Program, SequenceEntity
from psi.services import numbering as numbering_svc


def test_get_numbering_artifacts_falls_back_to_last_success_when_latest_non_success(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 10)
            p = Program(name="P-numbering-fallback", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-NUM", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            c = MoleculeComponent(
                molecule_id=int(m.id),
                role="HC1",
                fasta="EVQLVESGGGLVQPGGSLRLSCAASGFTF",
                sha256="x",
                created_at=now,
                updated_at=now,
            )
            db.add(c)
            db.commit()
            db.refresh(c)
            se = SequenceEntity(
                chain_id="CHAIN999",
                sha256="seqhash",
                sequence_norm="EVQLVESGGGLVQPGGSLRLSCAASGFTF",
                length=30,
                alphabet="AA",
                created_at=now,
            )
            db.add(se)
            db.commit()
            db.refresh(se)
            di = DomainInstance(
                molecule_id=int(m.id),
                component_id=int(c.id),
                domain_type="VH",
                start_idx=0,
                end_idx=30,
                domain_sequence_id=int(se.id),
                source="auto",
                method="test",
                status="success",
                created_at=now,
                updated_at=now,
            )
            db.add(di)
            db.commit()

            settings_hash = numbering_svc._settings_hash({"scheme": "kabat"})
            success_payload = {
                "scheme": "kabat",
                "chain_type": "VH",
                "positions": {},
                "labels_by_raw_index": ["H1", "H2"],
                "cdrs": {"FR1": "A", "CDR1": "B", "FR2": "C", "CDR2": "D", "FR3": "E", "CDR3": "F", "FR4": "G"},
                "spans": {},
                "warnings": [],
            }
            old_success = DomainArtifact(
                sequence_id=int(se.id),
                artifact_type="ab_numbering",
                domain_type="VH",
                tool_name="abnumber",
                tool_version="0.4.4",
                settings_hash=settings_hash,
                status="success",
                result_json=json.dumps(success_payload),
                error=None,
                created_at=now,
                updated_at=now,
            )
            latest_skipped = DomainArtifact(
                sequence_id=int(se.id),
                artifact_type="ab_numbering",
                domain_type="VH",
                tool_name="abnumber",
                tool_version="unavailable",
                settings_hash=settings_hash,
                status="skipped",
                result_json=None,
                error="dependency_missing",
                created_at=now,
                updated_at=now.replace(minute=now.minute + 1),
            )
            db.add(old_success)
            db.add(latest_skipped)
            db.commit()

            out = numbering_svc.get_numbering_artifacts_for_molecule(db, molecule_id=int(m.id), scheme="kabat")
            assert out["VH"] is not None
            assert out["VH"]["labels_by_raw_index"] == ["H1", "H2"]
            assert out["artifacts"]["VH"]["status"] == "skipped"
            assert out["artifacts"]["VH"]["using_last_success"] is True
        finally:
            db.close()
    finally:
        eng.dispose()

