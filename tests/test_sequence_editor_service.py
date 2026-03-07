from __future__ import annotations

from psi.services.sequence_editor import build_sequence_preview, normalize_mutation_queue, parse_mutation_notation


def test_parse_mutation_notation_accepts_comma_and_newline() -> None:
    rows, errors = parse_mutation_notation("Y2A,\nN4Q")
    assert errors == []
    assert [r["position"] for r in rows] == [2, 4]


def test_normalize_mutation_queue_validates_wt_and_sorts() -> None:
    queue, errors = normalize_mutation_queue(
        component_role="HC1",
        parent_sequence="MSGN",
        clicked_mutations=[{"position": 4, "from": "N", "to": "Q"}],
        direct_notation_text="S2A",
    )
    assert errors == []
    assert [q["position"] for q in queue] == [2, 4]
    assert queue[0]["to"] == "A"
    assert queue[1]["to"] == "Q"


def test_normalize_mutation_queue_detects_wt_mismatch() -> None:
    queue, errors = normalize_mutation_queue(
        component_role="HC1",
        parent_sequence="MSGN",
        clicked_mutations=[],
        direct_notation_text="T2A",
    )
    assert queue == []
    assert any("WT mismatch" in e for e in errors)


def test_build_sequence_preview_highlights_changes_and_errors() -> None:
    preview = build_sequence_preview(
        parent_sequence="MSGN",
        mutations=[
            {"position": 2, "from": "S", "to": "A"},
            {"position": 9, "from": "X", "to": "Q"},
        ],
    )
    assert preview["original_sequence"] == "MSGN"
    assert preview["edited_sequence"] == "MAGN"
    assert preview["changed_positions"] == [2]
    assert any("Out of range" in e for e in preview["errors"])
