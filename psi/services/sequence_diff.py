from __future__ import annotations

from typing import Any


# Rendering layout constant for deterministic monospaced row segmentation.
# Not user-configurable in v1 to keep the UI simple and predictable.
DEFAULT_DIFF_ROW_WIDTH = 64


def _norm_seq(value: str | None) -> str:
    return str(value or "").strip().upper()


def build_diff_rows(
    *,
    original: str | None,
    edited: str | None,
    row_width: int = DEFAULT_DIFF_ROW_WIDTH,
) -> list[dict[str, Any]]:
    """Build deterministic paired diff rows with per-residue changed flags.

    Output rows are render-ready for paired "Original"/"Edited" sequence displays.
    """
    o = _norm_seq(original)
    e = _norm_seq(edited)
    width = max(8, int(row_width or DEFAULT_DIFF_ROW_WIDTH))
    max_len = max(len(o), len(e))
    if max_len == 0:
        return []

    o_pad = o.ljust(max_len, "-")
    e_pad = e.ljust(max_len, "-")

    rows: list[dict[str, Any]] = []
    start = 0
    while start < max_len:
        end = min(max_len, start + width)
        orig_cells: list[dict[str, Any]] = []
        edit_cells: list[dict[str, Any]] = []
        changed_count = 0
        for i in range(start, end):
            oa = o_pad[i]
            ea = e_pad[i]
            changed = bool(oa != ea)
            if changed:
                changed_count += 1
            pos = int(i + 1)
            orig_cells.append({"aa": oa, "changed": changed, "position": pos})
            edit_cells.append({"aa": ea, "changed": changed, "position": pos})
        rows.append(
            {
                "start": int(start + 1),
                "end": int(end),
                "changed_count": int(changed_count),
                "original": orig_cells,
                "edited": edit_cells,
            }
        )
        start = end
    return rows

