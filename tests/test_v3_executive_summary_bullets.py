from __future__ import annotations

from psi.services.v3_board_reports import derive_executive_summary_bullets


def test_v3_executive_summary_bullets_are_rule_based_and_deterministic() -> None:
    kwargs = {
        "decision_state": "ready",
        "readiness_state": "ready",
        "blockers": [{"blocker_key": "B2"}, {"blocker_key": "B1"}],
        "comparability_summary": {"high_severity_count": 1},
        "evidence_summary_rows": [
            {"metric_key": "ec50", "total_count": 1, "usable_count": 1},
            {"metric_key": "percent_killing", "total_count": 3, "usable_count": 2},
        ],
    }
    a = derive_executive_summary_bullets(**kwargs)
    b = derive_executive_summary_bullets(**kwargs)
    assert a == b
    assert a["risks"] == sorted(a["risks"])
    assert a["required_actions"] == sorted(a["required_actions"])
    assert "policy_blockers_present" in a["risks"]
    assert "resolve_blocker:B1" in a["required_actions"]
    assert "resolve_blocker:B2" in a["required_actions"]

