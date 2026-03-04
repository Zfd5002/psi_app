from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from psi.services.reports_v3 import (
    build_molecule_board_display_from_payload,
    build_report_identity_summary,
)


class _NoQuerySession:
    def query(self, *_args, **_kwargs):  # pragma: no cover - raises by design
        raise AssertionError("view-time query not allowed")

    def get(self, *_args, **_kwargs):  # pragma: no cover - raises by design
        raise AssertionError("view-time object load not allowed")


def test_molecule_detail_board_display_is_payload_only_no_db_query() -> None:
    row = SimpleNamespace(id=1, report_type="molecule_report", created_at=datetime(2026, 3, 3, 12, 0, 0))
    payload = {
        "metadata": {"report_type": "molecule_report"},
        "sections": {
            "identity_context": {"molecule_id": 1, "program_id": 2, "primary_id": "M-1", "title": "Mol"},
            "fact_sheet": {
                "meta": {"as_of": "2026-03-03T11:00:00"},
                "metrics_index": {"metrics": [{"metric_key": "ec50", "group": "Potency"}]},
                "metric_matrix": {
                    "batch_columns": [{"batch_label": "B-1"}],
                    "rows": [{"metric_key": "ec50", "cells": [{"display": "12.0 nM"}]}],
                },
                "batch_registry": [{"batch_id": 1, "batch_label": "B-1"}],
                "coverage_summary": {"measurement_count": 1, "batch_count": 1},
                "best_batch": {"selected_batch_id": 1},
                "stability": {"status": "uncomputed", "rationale": []},
            },
            "artifacts": {"items": []},
            "reproducibility_appendix": {"measurement_keys": ["ec50"]},
        },
    }
    out = build_molecule_board_display_from_payload(row=row, payload=payload)
    assert out.get("header", {}).get("molecule") == "M-1"
    assert out.get("fact_sheet", {}).get("metric_rows")


def test_comparative_identity_summary_uses_payload_only_no_db_query() -> None:
    db = _NoQuerySession()
    payload = {
        "metadata": {"report_type": "molecule_comparative_report"},
        "sections": {
            "molecule_set": {
                "rows": [
                    {"molecule_id": 2, "primary_id": "M-B", "title": "Mol B"},
                    {"molecule_id": 1, "primary_id": "M-A", "title": "Mol A"},
                ]
            }
        },
    }
    identity = build_report_identity_summary(
        db,
        report_type="molecule_comparative_report",
        payload=payload,
        subject_ids=[2, 1],
        snapshot_coverage=[],
    )
    assert identity == "M-B (Mol B), M-A (Mol A)"
