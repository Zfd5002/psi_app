from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_evidence_detail_shows_capture_notice() -> None:
    tpl = _env().get_template("evidence/detail.html")
    html = tpl.render(
        request=SimpleNamespace(),
        ev=SimpleNamespace(
            id=4,
            domain="Biological",
            evidence_type="binding_support",
            strength=3,
            program_id=1,
            molecule_id=None,
            batch_id=None,
            created_at="2026-03-08",
            updated_at="2026-03-08",
            summary="S",
            details="",
        ),
        data_records=[],
        audits=[],
        capture_notice={"captured": True, "updated": False, "return_to": "/programs/1/workflow"},
    )
    assert "Capture recorded." in html
    assert "/programs/1/workflow" in html
