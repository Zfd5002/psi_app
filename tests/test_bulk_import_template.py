from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_data_list_template_has_bulk_import_link() -> None:
    tpl = _env().get_template("data/list.html")
    html = tpl.render(records=[])
    assert "/data/bulk-import" in html
    assert "Bulk import" in html


def test_bulk_import_template_renders_validate_and_confirm_forms() -> None:
    tpl = _env().get_template("data/bulk_import.html")
    html = tpl.render(
        request=SimpleNamespace(),
        pasted_text="",
        validated_rows=[{"row_num": 2, "molecule_id": 1, "molecule_primary_id": "M-1", "batch_label": "B-1", "metric_key": "kd_nM", "value_num": 9.0, "unit": "nM"}],
        errors=[],
        validated_json="[]",
        imported_count=None,
        message="",
    )
    assert "Bulk Data Import" in html
    assert 'action="/data/bulk-import"' in html
    assert "Validate rows" in html
    assert "Confirm import" in html
    assert "M-1" in html
