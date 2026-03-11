from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.core.models import Molecule, Program
from psi.web.routers import builder as builder_router


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_suggested_task_route_exists() -> None:
    route_keys = {(r.path, tuple(sorted(getattr(r, "methods", set()) or set()))) for r in builder_router.router.routes}
    assert ("/builder/suggested-task/new", ("GET",)) in route_keys


def test_suggested_task_route_prefills_payload(monkeypatch, mkdb, dummy_templates) -> None:
    eng, SessionTmp = mkdb()
    monkeypatch.setattr(builder_router, "get_templates", lambda _request: dummy_templates)
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 8)
            p = Program(name="P-sugg", created_at=now, updated_at=now)
            db.add(p); db.commit(); db.refresh(p)
            m = Molecule(program_id=int(p.id), primary_id="M-sugg", title="", created_at=now, updated_at=now)
            db.add(m); db.commit(); db.refresh(m)
            resp = builder_router.builder_suggested_task_new(
                request=SimpleNamespace(),
                molecule_id=int(m.id),
                metric_key="kd_nM",
                suggested_assay="BLI",
                suggested_rationale="close binding gap",
                db=db,
            )
            pre = resp.context["prefill"]
            assert int(pre["program_id"]) == int(p.id)
            assert str(pre["metric_key"]) == "kd_nM"
            assert str(pre["suggested_assay"]) == "BLI"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_molecule_governance_suggested_experiment_has_create_task_link() -> None:
    src = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "governance.html").read_text()
    assert "/builder/suggested-task/new?molecule_id={{ molecule.id }}" in src
    assert "Create Task" in src
