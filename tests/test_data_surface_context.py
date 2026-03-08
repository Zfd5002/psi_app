from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from psi.core.db import ensure_schema
from psi.core.models import Base, Batch, DataRecord, Molecule, Program
from psi.web.routers import data_records as data_records_router


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    with eng.begin() as conn:
        cols = conn.exec_driver_sql("PRAGMA table_info(data_measurements)").mappings().all()
        col_names = {str(r.get("name") or "") for r in cols}
        if "metric_key" not in col_names:
            conn.exec_driver_sql("ALTER TABLE data_measurements ADD COLUMN metric_key TEXT")
        if "name" in col_names:
            conn.execute(text("UPDATE data_measurements SET metric_key = COALESCE(metric_key, name)"))
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def _mk_request(path: str) -> Request:
    app = FastAPI()
    app.include_router(data_records_router.router)
    template_dir = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    app.state.templates = Jinja2Templates(directory=str(template_dir))
    scope = {"type": "http", "method": "GET", "path": path, "headers": [], "query_string": b"", "app": app}
    return Request(scope)


def test_new_data_route_sets_data_entry_surface() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-data-surface", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-D36", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            resp = data_records_router.new_data(
                request=_mk_request("/data/new"),
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=None,
                domain=None,
                data_type=None,
                method=None,
                title=None,
                task_id=None,
                db=db,
                rules_path=Path(__file__).resolve().parents[1] / "psi_rules" / "psirules-0.1.0.yml",
            )
            surface = dict(resp.context).get("surface") or {}
            assert surface.get("surface_key") == "data_entry"
            assert surface.get("surface_kind") == "workflow"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_data_detail_route_sets_data_detail_surface() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-data-detail", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-D37", title="m", created_at=now, updated_at=now)
            db.add(m)
            db.commit()
            db.refresh(m)
            b = Batch(molecule_id=int(m.id), batch_id="B-D37", title="b", created_at=now, updated_at=now)
            db.add(b)
            db.commit()
            db.refresh(b)
            rec = DataRecord(
                program_id=int(p.id),
                molecule_id=int(m.id),
                batch_id=int(b.id),
                domain="Biological",
                data_type="Binding",
                method="BLI",
                title="Rec",
                created_at=now,
                updated_at=now,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            resp = data_records_router.detail_data(record_id=int(rec.id), request=_mk_request(f"/data/{int(rec.id)}"), db=db)
            surface = dict(resp.context).get("surface") or {}
            assert surface.get("surface_key") == "data_detail"
            assert surface.get("surface_kind") == "workspace"
        finally:
            db.close()
    finally:
        eng.dispose()
