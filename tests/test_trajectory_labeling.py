from __future__ import annotations

from pathlib import Path


def test_molecule_trajectory_section_has_heuristic_label() -> None:
    src = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "governance.html").read_text()
    assert "Estimated outcome (heuristic projection)" in src


def test_board_trajectory_hints_have_heuristic_label() -> None:
    src = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "programs" / "board.html").read_text()
    assert "Estimated outcome (heuristic projection)" in src
    assert "Trajectory hint (estimated outcome):" in src
