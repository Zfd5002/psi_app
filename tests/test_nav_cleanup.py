from __future__ import annotations

from pathlib import Path


def test_navigation_standardizes_portfolio_path() -> None:
    src = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "base.html").read_text()
    assert 'href="/portfolio"' in src
    assert 'href="/portfolios"' not in src
