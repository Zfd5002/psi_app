from __future__ import annotations

from datetime import datetime

from psi.services.report_engine import (
    REPORT_TYPES,
    _order_molecule_comparative_rows,
    _order_program_comparative_rows,
    build_report_payload,
    canonical_report_json,
    canonical_report_json_bytes,
    create_report_request,
)
from psi.core.utils import stable_json_dumps
from psi.services.reports_v3 import get_v3_report_policy_pins
from psi.services.comparability import load_comparability_policy_latest


def test_v3_report_engine_fixed_schemas_deterministic_pytest():
    for rt in REPORT_TYPES:
        req = create_report_request(
            report_type=rt,
            subject_ids=[1, 2] if "comparative" in rt else [1],
            as_of=datetime(2026, 2, 26, 0, 0, 0),
            policy_pins={"report_policy": "v0"},
            snapshot_coverage=[2, 1, 2],
        )
        p1 = build_report_payload(req)
        p2 = build_report_payload(req)
        assert stable_json_dumps(p1) == stable_json_dumps(p2)
        assert p1["metadata"]["report_type"] == rt
        assert p1["metadata"]["snapshot_coverage"] == [1, 2]
        repro = p1["sections"]["reproducibility_appendix"]
        for k in ("policy_pins", "catalog_versions", "cited_snapshot_ids", "inputs_summary"):
            assert k in repro


def test_v3_report_policy_pins_deterministic_per_report_type():
    report_types = (
        "molecule_report",
        "program_report",
        "molecule_comparative_report",
        "program_comparative_report",
    )
    for rt in report_types:
        p1 = get_v3_report_policy_pins(rt)
        p2 = get_v3_report_policy_pins(rt)
        assert stable_json_dumps(p1) == stable_json_dumps(p2)
        assert p1["report_type"] == rt
        assert p1["template_catalog"]["catalog_id"] == "template_catalog_v0_1"


def test_v3_report_policy_pins_use_latest_comparability_policy() -> None:
    latest = load_comparability_policy_latest()
    pins = get_v3_report_policy_pins("molecule_report")
    comp_pin = pins.get("comparability_policy") if isinstance(pins.get("comparability_policy"), dict) else {}
    assert str(comp_pin.get("policy_id") or "") == str(latest.get("policy_id") or "")
    assert str(comp_pin.get("policy_version") or "") == str(latest.get("policy_version") or "")


def test_report_canonical_serialization_is_byte_stable_for_same_object():
    obj = {
        "z": 1,
        "a": {"k2": "β", "k1": 1.2300000000000},
        "list": [{"b": 2, "a": 1}, 3.5, "x"],
    }
    s1 = canonical_report_json(obj)
    s2 = canonical_report_json({"list": [{"a": 1, "b": 2}, 3.5, "x"], "a": {"k1": 1.23, "k2": "β"}, "z": 1})
    b1 = canonical_report_json_bytes(obj)
    b2 = canonical_report_json_bytes({"list": [{"a": 1, "b": 2}, 3.5, "x"], "a": {"k1": 1.23, "k2": "β"}, "z": 1})
    assert s1 == s2
    assert b1 == b2
    assert b1.decode("utf-8") == s1
    assert "e+" not in s1.lower() and "e-" not in s1.lower()


def test_comparative_row_ordering_contracts_are_deterministic():
    molecules = [
        {"molecule_id": 2, "primary_id": "M-B", "title": "B"},
        {"molecule_id": 1, "primary_id": "M-A", "title": "A"},
        {"molecule_id": 3, "primary_id": "M-B", "title": "A2"},
    ]
    programs = [
        {"program_id": 20, "name": "P2"},
        {"program_id": 10, "name": "P1"},
    ]
    m1 = _order_molecule_comparative_rows(molecules)
    m2 = _order_molecule_comparative_rows(list(reversed(molecules)))
    p1 = _order_program_comparative_rows(programs)
    p2 = _order_program_comparative_rows(list(reversed(programs)))
    assert [x["molecule_id"] for x in m1] == [1, 2, 3]
    assert [x["molecule_id"] for x in m1] == [x["molecule_id"] for x in m2]
    assert [x["program_id"] for x in p1] == [10, 20]
    assert [x["program_id"] for x in p1] == [x["program_id"] for x in p2]
