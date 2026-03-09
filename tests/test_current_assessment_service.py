from __future__ import annotations

from datetime import datetime

from psi.core.models import Batch, DecisionSnapshot, Molecule, Program
from psi.services import current_assessment as svc


def test_latest_active_snapshot_uses_supersession_semantics(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-current-assess", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-CA", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            s1 = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json='{"decision_state":"not_ready","gate_outcomes":{},"blockers":[]}',
                evidence_ids_json="[]",
                is_superseded=1,
                superseded_by_snapshot_id=2,
                created_at=now,
            )
            s2 = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json='{"decision_state":"ready","gate_outcomes":{},"blockers":[]}',
                evidence_ids_json="[]",
                is_superseded=0,
                superseded_by_snapshot_id=None,
                created_at=now,
            )
            db.add_all([s1, s2])
            db.commit()

            latest = svc.latest_active_snapshot_for_molecule(db, molecule_id=int(m.id))
            assert latest is not None
            assert int(latest.id) == int(s2.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_infer_molecule_scope_for_record_prefers_direct_then_batch(mkdb) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-scope", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-SCOPE", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-SCOPE", title="b", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            assert svc.infer_molecule_scope_for_record(db=db, molecule_id=int(m.id), batch_id=int(b.id)) == int(m.id)
            assert svc.infer_molecule_scope_for_record(db=db, molecule_id=None, batch_id=int(b.id)) == int(m.id)
            assert svc.infer_molecule_scope_for_record(db=db, molecule_id=None, batch_id=None) is None
        finally:
            db.close()
    finally:
        eng.dispose()


def test_refresh_current_assessment_reports_first_assessment_semantics(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-first", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-FIRST", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            def _fake_policy(_decision_key: str):
                return {"path": "/tmp/di.json"}

            def _fake_run_di(_db, *, di_input, policy_path):
                assert int(di_input.scope_id) == int(m.id)
                assert str(di_input.context.get("mode") or "") == "auto_current_assessment"
                assert str(policy_path) == "/tmp/di.json"
                return {
                    "snapshot_id": 101,
                    "output": {
                        "decision_state": "not_ready",
                        "gate_outcomes": {"g1": {"status": "hold", "missing": ["kd_nM"], "failed_metrics": []}},
                        "recommended_experiments": [{"metric_key": "kd_nM"}],
                    },
                }

            monkeypatch.setattr(svc, "_stable_default_policy_for_decision", _fake_policy)
            monkeypatch.setattr(svc, "run_di", _fake_run_di)

            out = svc.refresh_current_assessment_for_molecule(
                db,
                molecule_id=int(m.id),
                trigger="data_record_create",
            )
            assert out["refresh_semantics"] == "first_assessment"
            assert out["previous_snapshot_id"] is None
            assert out["state_label"] == "Missing Data"
            assert out["suggested_next_metric"] == "kd_nM"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_refresh_current_assessment_reports_updated_semantics_when_snapshot_exists(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-update", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-UPDATE", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            prev = DecisionSnapshot(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                decision_key="advance_to_in_vivo",
                rules_version="v1",
                inputs_json="{}",
                outputs_json='{"decision_state":"not_ready","gate_outcomes":{},"blockers":[]}',
                evidence_ids_json="[]",
                is_superseded=0,
                superseded_by_snapshot_id=None,
                created_at=now,
            )
            db.add(prev)
            db.commit()
            db.refresh(prev)

            def _fake_policy(_decision_key: str):
                return {"path": "/tmp/di.json"}

            def _fake_run_di(_db, *, di_input, policy_path):
                assert int(di_input.scope_id) == int(m.id)
                assert str(policy_path) == "/tmp/di.json"
                return {
                    "snapshot_id": 202,
                    "output": {
                        "decision_state": "ready",
                        "gate_outcomes": {"g1": {"status": "pass", "missing": [], "failed_metrics": []}},
                        "blockers": [],
                    },
                }

            monkeypatch.setattr(svc, "_stable_default_policy_for_decision", _fake_policy)
            monkeypatch.setattr(svc, "run_di", _fake_run_di)

            out = svc.refresh_current_assessment_for_molecule(
                db,
                molecule_id=int(m.id),
                trigger="data_record_create",
            )
            assert out["refresh_semantics"] == "updated_assessment"
            assert out["previous_snapshot_id"] == int(prev.id)
            assert out["state_label"] == "Ready"
        finally:
            db.close()
    finally:
        eng.dispose()
