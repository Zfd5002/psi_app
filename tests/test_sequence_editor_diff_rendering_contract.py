from __future__ import annotations

from pathlib import Path


def test_sequence_editor_js_uses_paired_diff_row_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    js = (root / "psi" / "web" / "static" / "sequence_editor.js").read_text(encoding="utf-8")
    assert "var SEQ_DIFF_ROW_WIDTH = 64;" in js
    assert "function buildDiffRows(original, edited, rowWidth)" in js
    assert "start: start + 1" in js
    assert "changed_count: changedCount" in js
    assert "original: origCells" in js
    assert "edited: editCells" in js
    assert 'id="seq_preview_rows"' not in js  # template-owned ID, JS should query by ID only
    assert 'var previewRows = byId("seq_preview_rows");' in js
    assert 'lineEl.className = "seq-diff-line";' in js
    assert 'aa.className = "seq-diff-aa" + (cell.changed ? " is-changed" : "");' in js

