from __future__ import annotations

import json
from pathlib import Path

from psi.services import molecule_header as mh


def _row(snapshot_id: int, created_at: str, template_key: str, decision_state: str, risk_flags_enriched=None):
    out = {"decision_state": decision_state}
    if risk_flags_enriched is not None:
        out["risk_flags_enriched"] = risk_flags_enriched
    return {
        "snapshot_id": snapshot_id,
        "created_at": created_at,
        "_in": {"template_key": template_key},
        "_out": out,
    }


def test_build_molecule_header_model_normalizes_moderate_and_keeps_unknown_neutral(monkeypatch):
    monkeypatch.setattr(mh, "_query_molecule_metric_keys_present", lambda db, molecule_id: ["expr_yield_mgL"])

    di_rows = [
        _row(
            1,
            "2026-02-26T00:00:00",
            "ready_for_scaleup_screen.v0_2",
            "ready",
            risk_flags_enriched=[
                {"key": "m_flag", "severity": "moderate"},
                {"key": "u_flag", "severity": "weird_new"},
            ],
        )
    ]
    model = mh._build_molecule_header_model(db=None, molecule_id=123, di_rows_chrono=di_rows)

    counts = model["risk_severity_counts"]
    assert counts["medium"] == 1
    assert counts["unspecified"] == 1
    assert counts["high"] == 0
    assert counts["low"] == 0

    items = {x["key"]: x for x in model["risk_items"]}
    assert items["m_flag"]["severity"] == "medium"
    assert items["u_flag"]["severity"] == "unspecified"
    assert items["u_flag"]["severity_neutral"] is True


def test_build_molecule_header_model_exposes_stage_advisory_items(monkeypatch):
    monkeypatch.setattr(mh, "_query_molecule_metric_keys_present", lambda db, molecule_id: ["expr_yield_mgL", "purity_percent"])

    # advance_to_in_vivo is "ready" but its prerequisite template is missing/failed, so UI advisory should trigger.
    di_rows = [
        _row(7, "2026-02-26T01:00:00", "advance_to_in_vivo.v0_5", "ready"),
        _row(6, "2026-02-25T23:00:00", "ready_for_scaleup_screen.v0_2", "not_ready"),
    ]
    model = mh._build_molecule_header_model(db=None, molecule_id=123, di_rows_chrono=di_rows)

    adv = model["progress_stage_advisory"]
    assert isinstance(adv, dict)
    assert isinstance(adv.get("blocked_by_items"), list)
    assert len(adv["blocked_by_items"]) >= 1
    assert "Blocked by prerequisites:" in (adv.get("blocked_by_text") or "")


def test_build_molecule_header_model_lock_fixture(monkeypatch):
    fixture_path = Path(__file__).parent / "fixtures" / "molecule_header_model_lock_v1.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    metrics_present = list(payload.get("metrics_present") or [])
    monkeypatch.setattr(mh, "_query_molecule_metric_keys_present", lambda db, molecule_id: metrics_present)

    model = mh._build_molecule_header_model(
        db=None,
        molecule_id=int(payload.get("molecule_id") or 0),
        di_rows_chrono=list(payload.get("di_rows_chrono") or []),
    )
    locked = {
        "progress_stage": model.get("progress_stage"),
        "progress_hover_text": model.get("progress_hover_text"),
        "progress_stage_advisory": model.get("progress_stage_advisory"),
        "risk_severity_counts": model.get("risk_severity_counts"),
        "risk_items": model.get("risk_items"),
        "confidence_model": model.get("confidence_model"),
        "progress_milestones": [
            {
                "key": m.get("key"),
                "kind": m.get("kind"),
                "label": m.get("label"),
                "satisfied": bool(m.get("satisfied")),
            }
            for m in (model.get("progress_milestones") or [])
        ],
    }
    assert locked == payload.get("expected")


def test_molecule_header_early_milestones_follow_explicit_display_order(monkeypatch):
    monkeypatch.setattr(
        mh,
        "_query_molecule_metric_keys_present",
        lambda db, molecule_id: ["expr_yield_mgL", "value_eu_ml", "pk_t12_h"],
    )
    model = mh._build_molecule_header_model(db=None, molecule_id=999, di_rows_chrono=[])
    keys = [str(m.get("key") or "") for m in (model.get("progress_milestones") or []) if isinstance(m, dict) and str(m.get("kind") or "") == "early"]
    assert keys[:3] == ["expression_present", "basic_qc_present", "purification_present"]
    assert "endotoxin_present" in keys
    assert "pk_screen_present" in keys
    assert keys.index("endotoxin_present") < keys.index("pk_screen_present")
