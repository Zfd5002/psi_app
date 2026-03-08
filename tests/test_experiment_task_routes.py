from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, ExperimentTask, Molecule, Program
from psi.web.routers import programs as programs_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_experiment_task_routes_exist() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in programs_router.router.routes}
    assert ("/programs/{program_id}/tasks/create", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/status", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/start", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/block", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/done", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/owner", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/due-date", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/urgency", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/{task_id}/notes", ("POST",)) in route_keys
    assert ("/programs/{program_id}/tasks/create-and-start-data", ("POST",)) in route_keys


def test_create_and_update_experiment_task_via_routes() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-routes", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-R1", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            resp = programs_router.create_experiment_task(
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
                owner_text="",
                due_date="",
                urgency="high",
                source_kind="board",
                source_snapshot_id=None,
                notes="initial",
                redirect_to="",
                db=db,
            )
            assert resp.status_code == 303
            rows = db.query(ExperimentTask).order_by(ExperimentTask.id.asc()).all()
            assert len(rows) == 1
            t = rows[0]
            assert str(t.metric_key or "") == "kd_nM"
            assert str(t.suggested_assay or "") == "SPR"
            assert str(t.status or "") == "planned"
            assert str(t.source_kind or "") == "board"

            resp = programs_router.start_experiment_task(program_id=int(p.id), task_id=int(t.id), redirect_to="", db=db)
            assert resp.status_code == 303
            db.refresh(t)
            assert str(t.status or "") == "in_progress"

            _ = programs_router.update_experiment_task_owner(
                program_id=int(p.id),
                task_id=int(t.id),
                owner_text="Dr. T",
                redirect_to="",
                db=db,
            )
            _ = programs_router.update_experiment_task_due_date(
                program_id=int(p.id),
                task_id=int(t.id),
                due_date="2026-03-12",
                redirect_to="",
                db=db,
            )
            _ = programs_router.update_experiment_task_urgency(
                program_id=int(p.id),
                task_id=int(t.id),
                urgency="critical",
                redirect_to="",
                db=db,
            )
            _ = programs_router.update_experiment_task_notes(
                program_id=int(p.id),
                task_id=int(t.id),
                notes="blocked on material",
                redirect_to="",
                db=db,
            )
            db.refresh(t)
            assert str(t.owner_text or "") == "Dr. T"
            assert str(t.due_date or "") == "2026-03-12"
            assert str(t.urgency or "") == "critical"
            assert str(t.notes or "") == "blocked on material"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_create_task_and_start_data_entry_route() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-task-start", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-R2", title="m2", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)

            resp = programs_router.create_task_and_start_data_entry(
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
                source_snapshot_id=None,
                db=db,
            )
            assert resp.status_code == 303
            loc = str(resp.headers.get("location") or "")
            assert loc.startswith("/data/new?")
            assert "program_id=1" in loc
            assert "molecule_id=1" in loc
            assert "task_id=" in loc
            rows = db.query(ExperimentTask).order_by(ExperimentTask.id.asc()).all()
            assert len(rows) == 1
            assert str(rows[0].source_kind or "") == "board"
            assert str(rows[0].metric_key or "") == "kd_nM"
        finally:
            db.close()
    finally:
        eng.dispose()
