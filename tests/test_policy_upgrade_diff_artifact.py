from __future__ import annotations

from psi.services.policy_upgrade import build_policy_diff_artifact, render_upgrade_delta_report_html
from psi.core.utils import stable_json_dumps
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base
from psi.services.policy_upgrade import (
    acknowledge_policy_upgrade_session,
    create_policy_upgrade_session,
    get_unacknowledged_upgrade_warnings,
    require_upgrade_acknowledged_for_semantic_actions,
    run_semantic_action_with_ack_guard,
    verify_policy_upgrade_session,
)


def test_policy_diff_artifact_is_deterministic_and_ordered():
    old_pins = {
        "ranking_policy": {"policy_id": "ranking_policy_v0_2", "enabled": False, "tie_break_contract_id": "tb.v1", "criteria_ids": ["c1", "c2"]},
        "comparability_policy": {"policy_id": "comparability_policy_v0_1", "rule_ids": ["R1", "R2"], "allowed_statuses": ["comparable"], "gating_behavior_id": "gate.v1"},
        "template_catalog": {
            "catalog_id": "template_catalog_v0_1",
            "template_keys": ["advance_to_in_vivo", "ready_for_scaleup_screen"],
            "current_versions": {"advance_to_in_vivo": "v0.4", "ready_for_scaleup_screen": "v0.1"},
            "immutable_versions": {"advance_to_in_vivo": ["v0.3", "v0.4"]},
        },
        "template_prerequisites": {"catalog_id": "template_prerequisites_v0_1"},
    }
    new_pins = {
        "comparability_policy": {"policy_id": "comparability_policy_v0_1", "rule_ids": ["R2", "R3"], "allowed_statuses": ["comparable", "incomparable"], "gating_behavior_id": "gate.v2"},
        "ranking_policy": {"policy_id": "ranking_policy_v0_2", "enabled": True, "tie_break_contract_id": "tb.v2", "criteria_ids": ["c2", "c3"]},
        "template_catalog": {
            "catalog_id": "template_catalog_v0_1",
            "template_keys": ["advance_to_in_vivo", "ready_for_scaleup_screen", "new_template"],
            "current_versions": {"advance_to_in_vivo": "v0.5", "ready_for_scaleup_screen": "v0.2"},
            "immutable_versions": {"advance_to_in_vivo": ["v0.3", "v0.4", "v0.5"]},
        },
        "template_prerequisites": {"catalog_id": "template_prerequisites_v0_2"},
    }
    a1 = build_policy_diff_artifact(old_policy_pins=old_pins, new_policy_pins=new_pins)
    a2 = build_policy_diff_artifact(old_policy_pins=dict(reversed(list(old_pins.items()))), new_policy_pins=dict(reversed(list(new_pins.items()))))
    assert stable_json_dumps(a1) == stable_json_dumps(a2)
    assert a1["artifact_type"] == "policy_upgrade_diff_v0"
    assert a1["changed_keys"] == ["comparability_policy", "ranking_policy", "template_catalog", "template_prerequisites"]
    assert isinstance(a1["old_policy_package_hash"], str) and len(a1["old_policy_package_hash"]) == 64
    report = a1["upgrade_delta_report"]
    assert report["schema_id"] == "upgrade_delta_report_v3"
    assert list(report.keys()) == ["schema_id", "schema_version", "header", "executive_summary_bullets", "change_table", "appendix"]
    assert [r["key"] for r in report["change_table"]["rows"]] == sorted([r["key"] for r in report["change_table"]["rows"]])
    ranking_delta = report["appendix"]["ranking_delta"]
    assert ranking_delta["enabled_flag_changes"]["changed"] is True
    assert ranking_delta["tie_break_contract_changes"]["changed"] is True
    assert ranking_delta["criteria_registry_changes"]["added"] == ["c3"]
    assert ranking_delta["criteria_registry_changes"]["removed"] == ["c1"]
    comparability_delta = report["appendix"]["comparability_delta"]
    assert comparability_delta["rule_registry_changes"]["added_rule_ids"] == ["R3"]
    assert comparability_delta["rule_registry_changes"]["removed_rule_ids"] == ["R1"]
    assert comparability_delta["allowed_status_changes"]["added_statuses"] == ["incomparable"]
    assert comparability_delta["gating_behavior_changes"]["changed"] is True
    template_delta = report["appendix"]["template_catalog_delta"]
    assert template_delta["template_key_changes"]["added"] == ["new_template"]
    assert template_delta["prerequisite_catalog_changes"]["changed"] is True


def test_upgrade_delta_report_html_rendering_is_available():
    payload = build_policy_diff_artifact(
        old_policy_pins={"ranking_policy": "v0.1"},
        new_policy_pins={"ranking_policy": "v0.2"},
    )
    html = render_upgrade_delta_report_html(delta_payload=payload)
    assert "Upgrade Delta Header" in html
    assert "Change Table" in html


def test_policy_upgrade_session_verification_requires_snapshot_set_and_inputs():
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            row_ok = create_policy_upgrade_session(
                db,
                old_policy_pins={"ranking_policy": "v0.1"},
                new_policy_pins={"ranking_policy": "v0.2"},
                snapshot_ids=[11],
                deterministic_inputs={"as_of": "2026-02-26T00:00:00"},
            )
            out = verify_policy_upgrade_session(db, session_id=int(row_ok.id))
            assert out["verified"] is True
            row_bad = create_policy_upgrade_session(
                db,
                old_policy_pins={"ranking_policy": "v0.1"},
                new_policy_pins={"ranking_policy": "v0.2"},
            )
            raised = False
            try:
                verify_policy_upgrade_session(db, session_id=int(row_bad.id))
            except ValueError as exc:
                raised = str(exc) == "policy_upgrade_session_missing_snapshot_set"
            assert raised
        finally:
            db.close()
    finally:
        eng.dispose()


def test_unacknowledged_semantic_delta_requires_action():
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            row = create_policy_upgrade_session(
                db,
                old_policy_pins={"ranking_policy": {"enabled": False}},
                new_policy_pins={"ranking_policy": {"enabled": True}},
                snapshot_ids=[1],
                deterministic_inputs={"as_of": "2026-02-26T00:00:00"},
            )
            warnings = get_unacknowledged_upgrade_warnings(db, current_policy_pins={"ranking_policy": {"enabled": True}})
            assert any(bool(w.get("action_required")) for w in warnings)
            assert any(str(w.get("action_label") or "") == "Action Required" for w in warnings)
            raised = False
            try:
                require_upgrade_acknowledged_for_semantic_actions(db, current_policy_pins={"ranking_policy": {"enabled": True}})
            except ValueError as exc:
                raised = str(exc) == "policy_upgrade_action_required"
            assert raised
            assert int(row.operator_acknowledged or 0) == 0
        finally:
            db.close()
    finally:
        eng.dispose()


def test_semantic_action_guard_wrapper_blocks_then_allows_after_ack() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            row = create_policy_upgrade_session(
                db,
                old_policy_pins={"ranking_policy": {"enabled": False}},
                new_policy_pins={"ranking_policy": {"enabled": True}},
                snapshot_ids=[1],
                deterministic_inputs={"as_of": "2026-02-26T00:00:00"},
            )
            blocked = False
            try:
                run_semantic_action_with_ack_guard(
                    db,
                    current_policy_pins={"ranking_policy": {"enabled": True}},
                    action=lambda: "ok",
                )
            except ValueError as exc:
                blocked = str(exc) == "policy_upgrade_action_required"
            assert blocked
            acknowledge_policy_upgrade_session(db, session_id=int(row.id), acknowledged=True)
            out = run_semantic_action_with_ack_guard(
                db,
                current_policy_pins={"ranking_policy": {"enabled": True}},
                action=lambda: "ok",
            )
            assert out == "ok"
        finally:
            db.close()
    finally:
        eng.dispose()
