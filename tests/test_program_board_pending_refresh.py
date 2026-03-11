from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from psi.core.models import DecisionSnapshot, Molecule, Program
from psi.web.routers import programs as programs_router


def test_board_update_pending_assessments_refreshes_not_evaluated_only(mkdb, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-board-refresh", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)

            m_pending = Molecule(program_id=int(p.id), primary_id="M-PENDING", title="pending", created_at=now, updated_at=now)
            m_ready = Molecule(program_id=int(p.id), primary_id="M-READY", title="ready", created_at=now, updated_at=now)
            db.add_all([m_pending, m_ready])
            db.commit()
            db.refresh(m_pending)
            db.refresh(m_ready)

            db.add(
                DecisionSnapshot(
                    program_id=int(p.id),
                    molecule_id=int(m_ready.id),
                    batch_id=None,
                    decision_key="advance_to_in_vivo",
                    rules_version="v1",
                    inputs_json="{}",
                    outputs_json='{"decision_state":"ready","gate_outcomes":{},"blockers":[]}',
                    evidence_ids_json="[]",
                    created_at=now,
                )
            )
            db.commit()

            seen: list[int] = []

            def _fake_refresh(_db, *, molecule_id: int, trigger: str, decision_key: str = "advance_to_in_vivo"):
                seen.append(int(molecule_id))
                assert trigger == "program_board_pending_refresh"
                return {"snapshot_id": 1, "decision_key": decision_key}

            monkeypatch.setattr(programs_router.assessment_svc, "refresh_current_assessment_for_molecule", _fake_refresh)

            resp = programs_router.program_board_update_pending_assessments(
                program_id=int(p.id),
                request=SimpleNamespace(),
                db=db,
            )
            assert resp.status_code == 303
            loc = str(resp.headers.get("location") or "")
            assert f"/programs/{int(p.id)}/board" in loc
            assert "pending_total=1" in loc
            assert "refreshed_pending=1" in loc
            assert seen == [int(m_pending.id)]
        finally:
            db.close()
    finally:
        eng.dispose()

