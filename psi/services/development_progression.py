from __future__ import annotations

from typing import Any

from psi.web.ui_labels import humanize_key, humanize_state

CANONICAL_DECISION_KEY = "advance_to_in_vivo"
CANONICAL_CHAIN_ID = "development_progression_v1"


def canonical_decision_key() -> str:
    return CANONICAL_DECISION_KEY


def canonical_chain_label() -> str:
    return humanize_key(CANONICAL_CHAIN_ID)


def decision_display_label(decision_key: str) -> str:
    return humanize_key(decision_key)


def _gate_order(output: dict[str, Any]) -> list[str]:
    gates = output.get("gates") if isinstance(output.get("gates"), list) else []
    from_gates = [
        str(g.get("gate_key") or "").strip()
        for g in gates
        if isinstance(g, dict) and str(g.get("gate_key") or "").strip()
    ]
    seen = set()
    ordered = []
    for gk in from_gates:
        if gk not in seen:
            seen.add(gk)
            ordered.append(gk)

    outcomes = output.get("gate_outcomes") if isinstance(output.get("gate_outcomes"), dict) else {}
    for gk in sorted(str(k) for k in outcomes.keys()):
        if gk not in seen:
            seen.add(gk)
            ordered.append(gk)
    return ordered


def build_progression_summary(output: dict[str, Any] | None) -> dict[str, Any]:
    out = output if isinstance(output, dict) else {}
    outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
    ordered_keys = _gate_order(out)

    stages: list[dict[str, Any]] = []
    for gk in ordered_keys:
        row = outcomes.get(gk) if isinstance(outcomes.get(gk), dict) else {}
        status = str(row.get("status") or row.get("outcome") or "not_assessed").strip().lower()
        missing = [str(x) for x in (row.get("missing") or []) if str(x).strip()]
        failed = [str(x) for x in (row.get("failed_metrics") or []) if str(x).strip()]
        stages.append(
            {
                "gate_key": gk,
                "stage_label": humanize_key(gk),
                "status": status,
                "status_label": humanize_state(status),
                "missing_metrics": missing,
                "missing_metric_labels": [humanize_key(x) for x in missing],
                "failed_metrics": failed,
                "failed_metric_labels": [humanize_key(x) for x in failed],
                "is_passed": status == "pass",
                "is_blocking": status not in {"pass", "ready"},
            }
        )

    passed = [s for s in stages if bool(s.get("is_passed"))]
    blocking = next((s for s in stages if bool(s.get("is_blocking"))), None)
    recs = [r for r in (out.get("recommended_experiments") or []) if isinstance(r, dict)]
    next_metric = str((recs[0].get("metric_key") if recs else "") or "").strip()
    next_step = f"Run assay for {humanize_key(next_metric)}." if next_metric else "Review molecule detail and create next experiment task."

    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    readiness_state = str(readiness.get("state") or "").strip().lower()
    decision_state = str(out.get("decision_state") or "").strip().lower()
    if readiness_state in {"ready", "blocked"}:
        overall = readiness_state
    elif decision_state in {"ready", "not_ready", "blocked"}:
        overall = decision_state
    elif stages:
        overall = "not_ready" if blocking else "ready"
    else:
        overall = "not_assessed"

    missing_reqs = list((blocking or {}).get("missing_metric_labels") or [])
    failing_reqs = list((blocking or {}).get("failed_metric_labels") or [])
    return {
        "chain_id": CANONICAL_CHAIN_ID,
        "chain_label": canonical_chain_label(),
        "decision_key": CANONICAL_DECISION_KEY,
        "decision_label": decision_display_label(CANONICAL_DECISION_KEY),
        "overall_status": overall,
        "overall_status_label": humanize_state(overall),
        "current_stage_label": (blocking.get("stage_label") if blocking else (stages[-1].get("stage_label") if stages else "Not assessed")),
        "blocking_stage_label": (blocking.get("stage_label") if blocking else ""),
        "passed_stage_labels": [str(s.get("stage_label") or "") for s in passed if str(s.get("stage_label") or "").strip()],
        "missing_requirement_labels": missing_reqs,
        "failing_requirement_labels": failing_reqs,
        "recommended_next_step": next_step,
        "stages": stages,
    }

