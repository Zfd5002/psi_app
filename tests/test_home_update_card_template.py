from __future__ import annotations

from pathlib import Path


def test_home_template_contains_check_only_update_card() -> None:
    src = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "home.html").read_text()
    assert "Windows User Updates" in src
    assert "Check for updates" in src
    assert "Check-only mode: this action does not download or apply updates." in src
