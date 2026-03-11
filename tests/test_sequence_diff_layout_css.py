from __future__ import annotations

from pathlib import Path


def test_seq_diff_css_pins_line_column_and_changed_highlight() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "psi" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".seq-diff-row .seq-diff-line{grid-column:2}" in css
    assert ".seq-diff-aa.is-changed" in css
    assert ".builder-draft-diff .seq-diff-aa.is-changed" in css
    assert ".builder-draft-diff .seq-diff-line{grid-template-columns:9ch 1fr}" in css
    assert ".builder-draft-diff .seq-diff-seq{white-space:nowrap;font-size:0}" in css
    assert "box-shadow" in css
