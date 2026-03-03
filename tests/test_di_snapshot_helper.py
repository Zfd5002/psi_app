from __future__ import annotations

from types import SimpleNamespace

from psi.services.di.util import is_di_snapshot_record


def test_is_di_snapshot_record_matches_expected_detection_modes() -> None:
    snap = SimpleNamespace(engine_key="", schema_version="")
    out = {"decision_state": "ready", "gates": []}
    inn = {}
    assert is_di_snapshot_record(snap, out, inn) is True

    snap2 = SimpleNamespace(engine_key="", schema_version="")
    out2 = {}
    inn2 = {"schema_version": "di.snapshot.v0_4"}
    assert is_di_snapshot_record(snap2, out2, inn2, include_input_schema_version=False) is False
    assert is_di_snapshot_record(snap2, out2, inn2, include_input_schema_version=True) is True
