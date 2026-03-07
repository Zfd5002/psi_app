from __future__ import annotations

from pathlib import Path

from psi.services.sequence_editor import build_sequence_preview, normalize_mutation_queue


def test_sequence_editor_queue_order_is_deterministic() -> None:
    queue, errors = normalize_mutation_queue(
        component_role="HC1",
        parent_sequence="ABCDEFG",
        clicked_mutations=[
            {"position": 7, "from": "G", "to": "Q"},
            {"position": 2, "from": "B", "to": "R"},
        ],
        direct_notation_text="D4E",
    )
    assert errors == []
    assert [int(q["position"]) for q in queue] == [2, 4, 7]
    assert [str(q["from"]) + str(q["position"]) + str(q["to"]) for q in queue] == ["B2R", "D4E", "G7Q"]


def test_sequence_editor_preview_is_pure_and_non_mutating() -> None:
    parent = "MSGN"
    parent_before = str(parent)
    preview = build_sequence_preview(
        parent_sequence=parent,
        mutations=[
            {"position": 4, "from": "N", "to": "Q"},
            {"position": 2, "from": "S", "to": "A"},
        ],
    )
    assert parent == parent_before
    assert preview["original_sequence"] == "MSGN"
    assert preview["edited_sequence"] == "MAGQ"
    assert preview["changed_positions"] == [2, 4]
    assert preview["errors"] == []


def test_sequence_editor_modules_remain_builder_only() -> None:
    root = Path(__file__).resolve().parents[1]
    py_text = (root / "psi" / "services" / "sequence_editor.py").read_text(encoding="utf-8")
    js_text = (root / "psi" / "web" / "static" / "sequence_editor.js").read_text(encoding="utf-8")
    forbidden = [
        "DecisionSnapshot",
        "ProgramMembership",
        "ReportRun",
        "run_di",
        "/programs/",
        "/reports/",
        "/di/",
    ]
    for tok in forbidden:
        assert tok not in py_text
        assert tok not in js_text
    assert "seq_to_builder_mutations" in js_text
    assert "seq_to_variant_mutation_tokens" in js_text
