from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
from psi.web.ui_labels import humanize_key

from psi.web.routers.reports import _board_template_for_report_type


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    env = Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))
    env.filters["humanize_key"] = humanize_key
    return env


def _render_detail(board_template_name: str) -> str:
    env = _env()
    tpl = env.get_template("reports/detail.html")
    return tpl.render(
        report_run=SimpleNamespace(id=9, report_type="x", as_of="2026-02-26", created_at="2026-02-26"),
        payload={"metadata": {"report_type": "x"}, "schema_id": "schema"},
        subject_ids=[1, 2],
        snapshot_coverage=[101, 102],
        identity_summary="X",
        board_template_name=board_template_name,
        board_narrative={
            "headline": "H",
            "status_rows": [],
            "what_this_means": [],
            "evidence_status": [],
            "determinations": [],
            "next_steps": [],
        },
        is_pdf=True,
    )


def test_board_template_mapping_deterministic() -> None:
    assert _board_template_for_report_type("molecule_report") == "reports/board_molecule_v3.html"
    assert _board_template_for_report_type("program_report") == "reports/board_program_v3.html"
    assert _board_template_for_report_type("molecule_comparative_report") == "reports/board_comparison_v3.html"


def test_detail_renders_molecule_board_template_sentinel() -> None:
    html = _render_detail("reports/board_molecule_v3.html")
    assert 'id="board-molecule-v3"' in html


def test_detail_renders_program_board_template_sentinel() -> None:
    html = _render_detail("reports/board_program_v3.html")
    assert 'id="board-program-v3"' in html


def test_detail_renders_comparison_board_template_sentinel() -> None:
    html = _render_detail("reports/board_comparison_v3.html")
    assert 'id="board-comparison-v3"' in html
