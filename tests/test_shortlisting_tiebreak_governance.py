from __future__ import annotations

from pathlib import Path

from psi.services.di.shortlisting import SHORTLISTING_INTERNAL_TIEBREAK_KEYS


def test_shortlisting_internal_tiebreak_keys_lock() -> None:
    assert SHORTLISTING_INTERNAL_TIEBREAK_KEYS == [
        "decision_ready_desc",
        "blockers_count_asc",
        "comparability_high_severity_asc",
        "metrics_present_desc",
        "metrics_missing_asc",
        "warnings_count_asc",
        "metrics_sourced_count_desc",
        "used_metric_count_desc",
        "ignored_count_asc",
        "warning_count_asc",
    ]


def test_shortlisting_runtime_has_no_weighted_tokens() -> None:
    p = Path(__file__).resolve().parents[1] / "psi" / "services" / "di" / "shortlisting.py"
    txt = p.read_text(encoding="utf-8")
    assert "\"ranking_weights\"" not in txt
    assert "\"weight\":" not in txt

