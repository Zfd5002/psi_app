from __future__ import annotations

from pathlib import Path


def test_sequence_viewer_uses_horizontal_scroll_not_clipping() -> None:
    css = (Path(__file__).resolve().parents[1] / "psi" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".seq-scroll{margin-top:10px;overflow-x:auto;" in css
    assert ".seq-scroll.viewer-v2 {" in css
    assert "overflow-x: auto !important;" in css
    assert ".seq-scroll.viewer-v2 .num-grid," in css
    assert ".seq-scroll.viewer-v2 .seq-grid {" in css
    assert "min-width: 0;" in css
    assert "width: 100%;" in css


def test_sequence_viewer_wrap_calc_is_conservative_and_reactive() -> None:
    js = (Path(__file__).resolve().parents[1] / "psi" / "web" / "static" / "molecule_detail.js").read_text(
        encoding="utf-8"
    )
    assert "const laneW = laneEl && laneEl.getBoundingClientRect ? laneEl.getBoundingClientRect().width : 0;" in js
    assert "const viewerW = viewerEl.getBoundingClientRect ? viewerEl.getBoundingClientRect().width : 0;" in js
    assert "const safetyPx = Math.max(1, cw * 0.15);" in js
    assert "Math.floor((usableWidth - safetyPx) / cw)" in js
    assert "const laneEl = viewerEl.querySelector('.lane');" in js
    assert "const w = laneW || viewerW;" in js
    assert "requestAnimationFrame(() => requestAnimationFrame(() => setWrapColsAll()))" in js
    assert "window.addEventListener(\"load\", scheduleWrapColsRefresh);" in js
    assert "if(window.ResizeObserver){" in js
    assert "viewerEl.style.setProperty('--residue-cell-w'" in js
    assert "if(!cw || !isFinite(cw) || cw < 7) cw = 10;" in js


def test_sequence_viewer_debug_mode_logs_runtime_geometry() -> None:
    js = (Path(__file__).resolve().parents[1] / "psi" / "web" / "static" / "molecule_detail.js").read_text(
        encoding="utf-8"
    )
    assert "searchParams.get('debug_seq')" in js
    assert "console.log('[PSI seq debug]'" in js
    assert "laneLabel" in js
    assert "seqGrid" in js
    assert "wrapCols" in js
    assert "residueCellW" in js


def test_sequence_viewer_grid_uses_measured_cell_width_variable() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "partials"
    seq_tpl = (root / "sequence_viewer.html").read_text(encoding="utf-8")
    hist_tpl = (root / "history_audit_zone.html").read_text(encoding="utf-8")
    expected = "grid-template-columns: repeat(var(--wrap-cols, 80), var(--residue-cell-w, 1ch));"
    assert expected in seq_tpl
    assert expected in hist_tpl
    assert 'action="/molecules/{{ molecule.id }}/numbering"' in seq_tpl
    assert "Compute numbering" in seq_tpl
    assert 'name="return_to" value="/molecules/{{ molecule.id }}/sequence#sequence-viewer"' in seq_tpl
    assert "numbering_status" in seq_tpl
    assert "missing_dependencies" in seq_tpl
    assert "numbering_missing" in seq_tpl
    assert "no_domains" in seq_tpl
    assert "domains_status" in seq_tpl
    assert "Annotation recompute started." in seq_tpl


def test_lane_allows_shrink_for_accurate_wrap_measurement() -> None:
    css = (Path(__file__).resolve().parents[1] / "psi" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".lane{margin:6px 0;min-width:0}" in css
