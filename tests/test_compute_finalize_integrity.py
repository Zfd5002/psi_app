from __future__ import annotations

from psi.core.di.schema import EvidenceRef
from psi.services.di.compute import _finalize_integrity


def _used_ref(mid: int) -> EvidenceRef:
    return EvidenceRef(
        measurement_id=mid,
        data_record_id=mid + 100,
        metric_key="hmw_pct",
        metric_key_source="canonical",
        value_num=1.0,
        value_text=None,
        value_bool=None,
        unit="%",
        comparator=None,
        qc_status="approved",
        qc_flag_raw=None,
        qc_source="measurement_qc",
        is_primary=True,
        is_outlier=False,
        produced_at=None,
        created_at="2026-02-26T00:00:00",
    )


def test_finalize_integrity_deterministic():
    out1 = {"provenance": {"integrity": {"evidence_fingerprint": "seed"}}}
    out2 = {"provenance": {"integrity": {"evidence_fingerprint": "seed"}}}
    inputs = {"decision_key": "advance_to_in_vivo", "scope_type": "batch", "scope_id": 1}
    used = {"hmw_pct": _used_ref(10)}

    _finalize_integrity(out=out1, inputs_obj=dict(inputs), used_by_metric=used)
    _finalize_integrity(out=out2, inputs_obj=dict(inputs), used_by_metric=used)

    i1 = out1["provenance"]["integrity"]
    i2 = out2["provenance"]["integrity"]
    assert i1 == i2
    assert i1["snapshot_content_hash"]
    assert i1["decision_output_hash"]
    assert i1["decision_output_hash_v2"]

