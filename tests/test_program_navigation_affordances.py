from __future__ import annotations

from pathlib import Path


def test_molecule_detail_has_program_workspace_action() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "detail.html").read_text(
        encoding="utf-8"
    )
    assert "Open Program Workspace" in tpl
    assert "\"/programs/\" ~ molecule.program_id" in tpl


def test_batch_detail_has_program_workspace_action() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "batches" / "detail.html").read_text(
        encoding="utf-8"
    )
    assert "Open Program Workspace" in tpl
    assert "/programs/{{ molecule.program_id }}" in tpl
