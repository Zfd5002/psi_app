from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services import dev_board as dev_board_svc
from psi.web.routers import programs as programs_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


class _DummyTemplates:
    @staticmethod
    def TemplateResponse(_name: str, ctx: dict):
        return SimpleNamespace(context=ctx)


def _mk_request(query: dict[str, str]):
    return SimpleNamespace(query_params=query)


def test_program_board_task_filters(monkeypatch) -> None:
    eng, SessionTmp = _mkdb()
    monkeypatch.setattr(programs_router, "get_templates", lambda _request: _DummyTemplates())
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-board-filters", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            mols = []
            for pid in ("M-F1", "M-F2", "M-F3", "M-F4"):
                m = Molecule(program_id=int(p.id), primary_id=pid, title=pid, created_at=now, updated_at=now)
                db.add(m)
                db.commit()
                db.refresh(m)
                mols.append(m)
                db.add(
                    DecisionSnapshot(
                        program_id=int(p.id),
                        molecule_id=int(m.id),
                        batch_id=None,
                        decision_key="advance_to_in_vivo",
                        rules_version="v1",
                        inputs_json="{}",
                        outputs_json=json.dumps({"decision_state": "ready", "gate_outcomes": {}, "blockers": []}),
                        evidence_ids_json="[]",
                        is_superseded=0,
                        created_at=now,
                    )
                )
                db.commit()
            today = date.today()
            db.add_all(
                [
                    ExperimentTask(
                        program_id=int(p.id),
                        molecule_id=int(mols[0].id),
                        status="in_progress",
                        owner_text="Dr A",
                        urgency="high",
                        due_date=(today + timedelta(days=2)).isoformat(),
                        created_at=now,
                        updated_at=now,
                    ),
                    ExperimentTask(
                        program_id=int(p.id),
                        molecule_id=int(mols[1].id),
                        status="blocked",
                        owner_text="Dr B",
                        urgency="low",
                        due_date=(today - timedelta(days=1)).isoformat(),
                        created_at=now,
                        updated_at=now,
                    ),
                    ExperimentTask(
                        program_id=int(p.id),
                        molecule_id=int(mols[2].id),
                        status="planned",
                        owner_text="",
                        urgency="critical",
                        due_date="",
                        created_at=now,
                        updated_at=now,
                    ),
                    ExperimentTask(
                        program_id=int(p.id),
                        molecule_id=int(mols[3].id),
                        status="done",
                        owner_text="Dr C",
                        urgency="normal",
                        due_date=(today + timedelta(days=1)).isoformat(),
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            db.commit()
            dev_board_svc.invalidate_program_board_cache(program_id=int(p.id))

            def _ids(resp):
                groups = resp.context["board"]["groups"]
                return sorted([str(r.get("primary_id")) for key in ("ready", "failed", "missing_data", "not_evaluated") for r in (groups.get(key) or [])])

            base = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({}), db=db)
            assert _ids(base) == ["M-F1", "M-F2", "M-F3", "M-F4"]

            owner = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({"owner": "dr b"}), db=db)
            assert _ids(owner) == ["M-F2"]

            urg = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({"urgency": "critical"}), db=db)
            assert _ids(urg) == ["M-F3"]

            due_soon = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({"due": "due_soon"}), db=db)
            assert _ids(due_soon) == ["M-F1"]

            overdue = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({"due": "overdue"}), db=db)
            assert _ids(overdue) == ["M-F2"]

            blocked = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({"task_status": "blocked"}), db=db)
            assert _ids(blocked) == ["M-F2"]

            open_only = programs_router.program_development_board(program_id=int(p.id), request=_mk_request({"task_status": "open"}), db=db)
            assert _ids(open_only) == ["M-F1", "M-F2", "M-F3"]
        finally:
            db.close()
    finally:
        eng.dispose()
