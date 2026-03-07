from __future__ import annotations

from psi.services.builder_ops import apply_point_mutations, parse_point_mutation_tokens


def test_parse_point_mutation_tokens_accepts_multiple_tokens_deterministically() -> None:
    muts, errors = parse_point_mutation_tokens("S2A N4Q")
    assert errors == []
    assert [m.token for m in muts] == ["S2A", "N4Q"]
    assert [m.position for m in muts] == [2, 4]


def test_parse_point_mutation_tokens_rejects_invalid_and_duplicate_positions() -> None:
    muts, errors = parse_point_mutation_tokens("S2A BAD N2Q")
    assert len(muts) == 1
    assert muts[0].token == "S2A"
    assert "Invalid mutation token: BAD" in errors
    assert "Duplicate mutation position: 2" in errors


def test_apply_point_mutations_validates_wt_and_applies_in_input_order() -> None:
    muts, errors = parse_point_mutation_tokens("S2A N4Q")
    assert errors == []
    mutated, apply_errors = apply_point_mutations(sequence="MSGN", mutations=muts)
    assert apply_errors == []
    assert mutated == "MAGQ"


def test_apply_point_mutations_reports_wt_mismatch_without_crash() -> None:
    muts, errors = parse_point_mutation_tokens("T2A")
    assert errors == []
    mutated, apply_errors = apply_point_mutations(sequence="MSGN", mutations=muts)
    assert mutated == "MSGN"
    assert "WT mismatch at position 2: expected T, found S" in apply_errors
