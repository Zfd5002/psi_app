from __future__ import annotations

from datetime import datetime

from psi.core.models import Batch, DataRecord, Molecule, Program
from psi.web.routers import data_records as data_router


def _seed_scope(db):
    now = datetime(2026, 3, 9)
    p = Program(name="P-auto-refresh", created_at=now, updated_at=now)
    db.add(p)
    db.commit()
    db.refresh(p)
    m = Molecule(program_id=int(p.id), primary_id="M-AR", title="m", created_at=now, updated_at=now)
    db.add(m)
    db.commit()
    db.refresh(m)
    b = Batch(molecule_id=int(m.id), batch_id="B-AR", title="b", created_at=now, updated_at=now)
    db.add(b)
    db.commit()
    db.refresh(b)
    return p, m, b


def test_create_data_triggers_current_assessment_refresh(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            p, m, b = _seed_scope(db)
            seen: dict[str, object] = {}

            def _fake_refresh(_db, *, molecule_id: int, trigger: str, decision_key: str = "advance_to_in_vivo"):
                seen["molecule_id"] = int(molecule_id)
                seen["trigger"] = str(trigger)
                seen["decision_key"] = str(decision_key)
                return {
                    "refresh_semantics": "first_assessment",
                    "state_label": "Missing Data",
                    "suggested_next_metric": "kd_nM",
                    "strongest_blocking_metrics": ["kd_nM"],
                }

            monkeypatch.setattr(data_router.assessment_svc, "refresh_current_assessment_for_molecule", _fake_refresh)

            resp = data_router.create_data(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="AR create",
                task_id=None,
                action_intent="save",
                return_to="",
                notes="",
                run_date="2026-03-09",
                params_json="{}",
                results_json='{"kd_nM": 99}',
                files=[],
                db=db,
                storage=None,
            )
            assert resp.status_code == 303
            location = str(resp.headers.get("location") or "")
            assert "assessment_semantics=first_assessment" in location
            assert seen["molecule_id"] == int(m.id)
            assert seen["trigger"] == "data_record_create"
            assert seen["decision_key"] == "advance_to_in_vivo"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_update_data_triggers_current_assessment_refresh(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            p, m, b = _seed_scope(db)
            now = datetime(2026, 3, 9)
            rec = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="AR existing",
                params_json="{}",
                results_json='{"kd_nM": 200}',
                raw_inputs_json="{}",
                derived_outputs_json='{"kd_nM": 200}',
                created_at=now,
                updated_at=now,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)

            seen: dict[str, object] = {}

            def _fake_refresh(_db, *, molecule_id: int, trigger: str, decision_key: str = "advance_to_in_vivo"):
                seen["molecule_id"] = int(molecule_id)
                seen["trigger"] = str(trigger)
                return {
                    "refresh_semantics": "updated_assessment",
                    "state_label": "Failed Criteria",
                    "suggested_next_metric": "",
                    "strongest_blocking_metrics": ["ec50_nM"],
                }

            monkeypatch.setattr(data_router.assessment_svc, "refresh_current_assessment_for_molecule", _fake_refresh)

            resp = data_router.update_data(
                record_id=int(rec.id),
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="AR updated",
                notes="",
                run_date="2026-03-09",
                params_json="{}",
                results_json='{"kd_nM": 180}',
                reason="",
                action_intent="save",
                actor="scientist",
                qc_note="",
                return_to="",
                files=[],
                db=db,
                storage=None,
            )
            assert resp.status_code == 303
            location = str(resp.headers.get("location") or "")
            assert "assessment_semantics=updated_assessment" in location
            assert seen["molecule_id"] == int(m.id)
            assert seen["trigger"] == "data_record_update"
        finally:
            db.close()
    finally:
        eng.dispose()
