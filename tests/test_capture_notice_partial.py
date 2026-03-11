from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_capture_notice_partial_renders_return_link_and_flags() -> None:
    tpl = _env().get_template("partials/capture_notice.html")
    html = tpl.render(
        capture_notice={
            "captured": True,
            "updated": True,
            "from_task": True,
            "next_step": "evidence",
            "return_to": "/programs/1/workflow",
            "message": "",
        }
    )
    assert "Capture recorded." in html
    assert "Update recorded." in html
    assert "Task-linked flow." in html
    assert "Optional next step: create or link evidence from this result if you need interpretation/governance documentation." in html
    assert "/programs/1/workflow" in html
