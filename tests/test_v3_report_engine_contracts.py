from __future__ import annotations

from datetime import datetime

from psi.services.report_engine import (
    REPORT_TYPES,
    build_report_payload,
    create_report_request,
)
from psi.core.utils import stable_json_dumps
from psi.services.reports_v3 import get_v3_report_policy_pins


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
