from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

from psi.web.routers import programs as programs_router


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_program_board_route_exists() -> None:
    route_keys = {
        (r.path, tuple(sorted(getattr(r, "methods", set()) or set())))
        for r in programs_router.router.routes
    }
    assert ("/programs/{program_id}/board", ("GET",)) in route_keys


def test_program_board_template_renders_sections() -> None:
    tpl = _env().get_template("programs/board.html")
    html = tpl.render(
        request=SimpleNamespace(),
        program=SimpleNamespace(id=1, name="P1"),
        board_filter="all",
        board_query="M-2",
        board={
            "groups": {
                "ready": [{"molecule_id": 2, "primary_id": "M-2", "status": "ready", "blocking_reason": "", "trend_signal": "improving", "missing_metrics": ["kd_nM"], "recommended_experiments": [{"metric_key": "kd_nM"}], "warnings": ["confirmation recommended"]}],
                "failed": [],
                "missing_data": [],
                "not_evaluated": [],
            }
        },
    )
    assert "Development Board" in html
    assert "READY" in html
    assert "FAILED CRITERIA" in html
    assert "MISSING DATA" in html
    assert "NOT EVALUATED" in html
    assert "Program Summary" in html
    assert "Ready:" in html
    assert "> 1<" in html
    assert "/programs/1/board?filter=ready" in html
    assert "Search molecule ID" in html
    assert 'name="q"' in html
    assert "/molecules/2" in html
    assert 'id="board-ready"' in html
    assert "count=1" in html
    assert "Status: ready" in html
    assert "▲ improving" in html
    assert 'data-card-link="/molecules/2"' in html
    assert "Add missing measurement" in html
    assert "Run suggested experiment" in html
    assert "/data/new?program_id=1" in html
    assert "molecule_id=2" in html
    assert "/builder/point-mutation?parent_molecule_id=2" in html
    assert "/molecules/2#sequence-editor" in html
    assert "⚠ confirmation recommended" in html
