from __future__ import annotations

from pathlib import Path


def test_board_template_includes_localstorage_filter_persistence() -> None:
    src = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "programs" / "board.html").read_text()
    assert "psi.board.filters.program." in src
    assert "window.localStorage.setItem(storageKey" in src
    assert "window.localStorage.getItem(storageKey" in src
    assert "boardSearchForm" in src
    assert "boardTaskFiltersForm" in src
