from __future__ import annotations

import re

from psi.core.utils import stable_json_dumps
from psi.services.v3_narrative import (
    render_molecule_comparison_narrative,
    render_molecule_narrative,
    render_program_comparison_narrative,
    render_program_narrative,
)


_HEX64_RE = re.compile(r"\b[a-f0-9]{64}\b", flags=re.IGNORECASE)


def test_molecule_narrative_handles_missing_sections_deterministically() -> None:
    payload = {
        "metadata": {"report_type": "molecule_report"},
        "sections": {
            "identity_context": {"molecule_id": 8, "primary_id": "M8"},
            "experimental_gaps": [],
            "reproducibility_appendix": {},
        },
    }
    a = render_molecule_narrative(payload)
    b = render_molecule_narrative(payload)
    assert stable_json_dumps(a) == stable_json_dumps(b)
    joined = stable_json_dumps(a)
    assert "Evidence is not yet captured in PSI (0 snapshots)." in joined
    assert "No cited measurements in this report." in joined


def test_narrative_is_deterministic_for_all_report_types() -> None:
    payload = {"metadata": {"report_type": "program_report"}, "sections": {"identity_context": {"program_name": "P1"}}}
    out = [
        render_molecule_narrative(payload),
        render_program_narrative(payload),
        render_molecule_comparison_narrative(payload),
        render_program_comparison_narrative(payload),
    ]
    out2 = [
        render_molecule_narrative(payload),
        render_program_narrative(payload),
        render_molecule_comparison_narrative(payload),
        render_program_comparison_narrative(payload),
    ]
    assert stable_json_dumps(out) == stable_json_dumps(out2)


def test_narrative_hides_hash_like_tokens() -> None:
    payload = {
        "metadata": {"report_type": "molecule_report"},
        "sections": {
            "identity_context": {"primary_id": "M1"},
            "experimental_gaps": ["fill_data_for_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
        },
    }
    out = render_molecule_narrative(payload)
    raw = stable_json_dumps(out)
    assert _HEX64_RE.search(raw) is None


def test_board_narratives_do_not_emit_hex_hash_tokens() -> None:
    payload = {
        "metadata": {"report_type": "program_report"},
        "sections": {
            "identity_context": {"program_name": "P1"},
            "experimental_gaps": ["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
        },
    }
    rendered = [
        render_molecule_narrative(payload),
        render_program_narrative(payload),
        render_molecule_comparison_narrative(payload),
        render_program_comparison_narrative(payload),
    ]
    for obj in rendered:
        assert _HEX64_RE.search(stable_json_dumps(obj)) is None


def test_comparison_narrative_uses_friendly_subject_labels_and_no_array_literal() -> None:
    payload = {
        "metadata": {"report_type": "molecule_comparison_report"},
        "sections": {
            "identity_context": {"subjects": [1, 2]},
            "molecule_set": {
                "rows": [
                    {"molecule_id": 1, "primary_id": "M1", "title": "Mol One"},
                    {"molecule_id": 2, "primary_id": "M2", "title": "Mol Two"},
                ]
            },
            "experimental_gaps": [],
        },
    }
    out = render_molecule_comparison_narrative(payload)
    raw = stable_json_dumps(out)
    assert "M1 (Mol One), M2 (Mol Two)" in raw
    status_row = next((x for x in out["status_rows"] if x.get("label") == "Subjects"), {})
    assert status_row.get("value") == "M1 (Mol One), M2 (Mol Two)"


def test_molecule_narrative_uses_decision_state_and_experimental_gap_lists() -> None:
    payload = {
        "metadata": {"report_type": "molecule_report"},
        "sections": {
            "identity_context": {"molecule_id": 9, "primary_id": "M9"},
            "stage_determination": {"decision_state": "ready", "readiness_state": "not_ready"},
            "experimental_gaps": {
                "blockers": ["missing_pk_window"],
                "next_best_experiments": ["repeat_pk"],
            },
        },
    }
    out = render_molecule_narrative(payload)
    stage_row = next((x for x in out["status_rows"] if x.get("label") == "Stage"), {})
    assert stage_row.get("value") == "ready"
    assert out["next_steps"] == ["missing_pk_window"]


def test_program_comparison_narrative_uses_program_set_rows() -> None:
    payload = {
        "metadata": {"report_type": "program_comparison_report"},
        "sections": {
            "program_set": {
                "rows": [
                    {"program_id": 2, "molecule_count": 5},
                    {"program_id": 7, "molecule_count": 1},
                ]
            }
        },
    }
    out = render_program_comparison_narrative(payload)
    status_row = next((x for x in out["status_rows"] if x.get("label") == "Subjects"), {})
    assert status_row.get("value") == "program_id=2 (molecules=5), program_id=7 (molecules=1)"


def test_program_narrative_headline_uses_metadata_program_identity() -> None:
    payload = {
        "metadata": {"report_type": "program_report"},
        "sections": {
            "metadata": {"program_id": 42},
            "next_best_experiments": {"items": []},
        },
    }
    out = render_program_narrative(payload)
    assert out["headline"] == "Program report for program_id=42"
    program_row = next((x for x in out["status_rows"] if x.get("label") == "Program"), {})
    assert program_row.get("value") == "program_id=42"


def test_program_narrative_next_steps_uses_next_best_experiments_items() -> None:
    payload = {
        "metadata": {"report_type": "program_report"},
        "sections": {
            "metadata": {"program_id": 99},
            "next_best_experiments": {
                "items": [
                    {"suggestion_key": "run_pk_panel", "label": "Run PK panel"},
                    {"suggestion_key": "extend_ada"},
                ]
            },
        },
    }
    out = render_program_narrative(payload)
    assert out["next_steps"] == ["Run PK panel", "extend_ada"]


def test_program_narrative_next_steps_prefers_next_best_experiments_items_over_other_fields() -> None:
    payload = {
        "metadata": {"report_type": "program_report"},
        "sections": {
            "metadata": {"program_id": 77},
            "experimental_gaps": {"blockers": ["do_not_use_this_for_program"]},
            "next_best_experiments": {
                "items": [
                    {"suggestion_key": "run_pk_panel", "label": "Run PK panel."},
                    {"suggestion_key": "ada_followup", "label": "Run ADA follow-up.."},
                ]
            },
        },
    }
    out = render_program_narrative(payload)
    assert out["next_steps"] == ["Run PK panel.", "Run ADA follow-up."]


def test_narrative_what_this_means_normalizes_spacing_and_terminal_punctuation() -> None:
    payload = {
        "metadata": {"report_type": "program_report"},
        "sections": {"metadata": {"program_id": 12}},
    }
    out = render_program_narrative(payload)
    assert out["what_this_means"]
    first = out["what_this_means"][0]
    assert "  " not in first
    assert ".." not in first
    assert first.endswith(".")
