from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _env() -> Environment:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates"
    return Environment(loader=FileSystemLoader(str(root)), autoescape=select_autoescape(["html", "xml"]))


def test_base_navigation_includes_portfolio_link() -> None:
    tpl = _env().get_template("base.html")
    html = tpl.render(request=SimpleNamespace(), PSI_VERSION="v-test")
    assert 'href="/portfolio"' in html
    assert 'href="/claims"' in html
    assert 'href="/plans"' in html
