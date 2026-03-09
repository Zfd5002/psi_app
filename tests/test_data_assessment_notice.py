from __future__ import annotations

from psi.web.routers import data_records as data_router


def test_assessment_notice_message_first_assessment() -> None:
    msg = data_router._assessment_notice_message(
        {
            "semantics": "first_assessment",
            "state": "Missing Data",
            "blocker": "kd_nM",
            "next_metric": "kd_nM",
            "error": "",
        }
    )
    assert "first current assessment" in msg
    assert "Current status: Missing Data." in msg
    assert "Remaining blocker: kd_nM." in msg


def test_assessment_notice_message_updated_assessment() -> None:
    msg = data_router._assessment_notice_message(
        {
            "semantics": "updated_assessment",
            "state": "Ready",
            "blocker": "",
            "next_metric": "",
            "error": "",
        }
    )
    assert "updated the current assessment" in msg
    assert "Current status: Ready." in msg
