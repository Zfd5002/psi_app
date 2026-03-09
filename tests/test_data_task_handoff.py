from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, DataRecord, ExperimentTask, Molecule, Program
from psi.web.routers import data_records as data_records_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _mk_request(path: str = "/data/new") -> Request:
    app = FastAPI()
    template_dir = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    app.state.templates = Jinja2Templates(directory=str(template_dir))
    scope = {"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b"", "app": app}
    return Request(scope)


def test_data_new_task_handoff_prefills_context() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-data-task", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-D1", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            t = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="SPR",
                status="in_progress",
                owner_text="Dr. A",
                due_date="2026-03-12",
                urgency="high",
                notes="Task handoff note",
                created_at=now,
                updated_at=now,
            )
            db.add(t)
            db.commit()
            db.refresh(t)

            resp = data_records_router.new_data(
                request=_mk_request(),
                program_id=None,
                molecule_id=None,
                batch_id=None,
                domain=None,
                data_type=None,
                method=None,
                title=None,
                task_id=int(t.id),
                db=db,
                rules_path=Path(__file__).resolve().parents[1] / "psi_rules" / "psirules-0.1.0.yml",
            )
            ctx = dict(resp.context)
            assert int(ctx["prefill"]["program_id"]) == int(p.id)
            assert int(ctx["prefill"]["molecule_id"]) == int(m.id)
            assert str(ctx["prefill"]["method"]) == "SPR"
            assert "Run kd_nM experiment" in str(ctx["prefill"]["title"])
            assert int(ctx["task_context"]["task_id"]) == int(t.id)
            assert str(ctx["task_context"]["metric_key"]) == "kd_nM"
            assert str(ctx["task_context"]["suggested_assay"]) == "SPR"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_create_data_with_task_id_links_and_completes_task() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="P-data-task-create", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-D2", title="m2", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-1", title="B1", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)
            t = ExperimentTask(
                program_id=int(p.id),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="BLI",
                status="planned",
                source_kind="board",
                created_at=now,
                updated_at=now,
            )
            db.add(t)
            db.commit()
            db.refresh(t)

            resp = data_records_router.create_data(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Task-linked run",
                task_id=int(t.id),
                action_intent="save",
                notes="",
                run_date="2026-03-07",
                params_json="{}",
                results_json="{\"kd_nM\": 3.2}",
                files=[],
                db=db,
                storage=None,
            )
            assert resp.status_code == 303
            assert str(resp.headers.get("location") or "").startswith("/data/")
            rec = db.query(DataRecord).order_by(DataRecord.id.desc()).first()
            assert rec is not None
            db.refresh(t)
            assert int(t.linked_data_record_id) == int(rec.id)
            assert str(t.status) == "done"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_new_data_batch_prefill_infers_molecule_and_program() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 9)
            p = Program(name="P-data-batch-prefill", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-D3", title="m3", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-3", title="B3", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)

            resp = data_records_router.new_data(
                request=_mk_request(),
                program_id=None,
                molecule_id=None,
                batch_id=int(b.id),
                domain=None,
                data_type=None,
                method=None,
                title=None,
                task_id=None,
                db=db,
                rules_path=Path(__file__).resolve().parents[1] / "psi_rules" / "psirules-0.1.0.yml",
            )
            ctx = dict(resp.context)
            assert int(ctx["prefill"]["batch_id"]) == int(b.id)
            assert int(ctx["prefill"]["molecule_id"]) == int(m.id)
            assert int(ctx["prefill"]["program_id"]) == int(p.id)
        finally:
            db.close()
    finally:
        eng.dispose()
