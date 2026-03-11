from __future__ import annotations

from psi.services.sequence_diff import build_diff_rows


def test_build_diff_rows_marks_changed_positions_deterministically() -> None:
    rows = build_diff_rows(original="MSGN", edited="MAGQ", row_width=8)
    assert len(rows) == 1
    r0 = rows[0]
    assert r0["start"] == 1
    assert r0["end"] == 4
    assert r0["changed_count"] == 2
    changed_positions = [int(c["position"]) for c in r0["original"] if bool(c["changed"])]
    changed_positions_edited = [int(c["position"]) for c in r0["edited"] if bool(c["changed"])]
    assert changed_positions == [2, 4]
    assert changed_positions_edited == [2, 4]
    assert "".join(str(c["aa"]) for c in r0["original"]) == "MSGN"
    assert "".join(str(c["aa"]) for c in r0["edited"]) == "MAGQ"


def test_build_diff_rows_segments_into_stable_rows() -> None:
    rows = build_diff_rows(original=("A" * 130), edited=("A" * 129 + "G"), row_width=64)
    assert [int(r["start"]) for r in rows] == [1, 65, 129]
    assert [int(r["end"]) for r in rows] == [64, 128, 130]
    assert int(rows[-1]["changed_count"]) == 1
