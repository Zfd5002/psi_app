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
            "II_general_profile": {
                "columns": [
                    {"primary_id": "M1", "title": "Mol One"},
                    {"primary_id": "M2", "title": "Mol Two"},
                ]
            },
            "experimental_gaps": [],
        },
    }
    out = render_molecule_comparison_narrative(payload)
    raw = stable_json_dumps(out)
    assert "M1 (Mol One), M2 (Mol Two)" in raw
    assert "[]" not in raw
