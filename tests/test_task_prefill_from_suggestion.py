from __future__ import annotations

from psi.services.experiment_tasks import build_task_prefill_from_suggestion


def test_build_task_prefill_from_suggestion_maps_deterministically() -> None:
    out = build_task_prefill_from_suggestion(
        program_id=5,
        molecule_id=9,
        metric_key="kd_nM",
        suggested_assay="BLI",
        suggested_rationale="close affinity gap",
        source_kind="insight",
    )
    assert out == {
        "program_id": 5,
        "molecule_id": 9,
        "metric_key": "kd_nM",
        "suggested_assay": "BLI",
        "suggested_rationale": "close affinity gap",
        "source_kind": "insight",
    }


def test_build_task_prefill_from_suggestion_falls_back_to_metric_for_assay() -> None:
    out = build_task_prefill_from_suggestion(
        program_id=1,
        molecule_id=2,
        metric_key="sec_monomer_pct",
        suggested_assay="",
        suggested_rationale="",
        source_kind="unexpected",
    )
    assert out["suggested_assay"] == "sec_monomer_pct"
    assert out["source_kind"] == "insight"
