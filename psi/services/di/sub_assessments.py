from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple


def baseline_risk_flags_from_used(*, used_by_metric: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic baseline risk flags shared across templates."""

    out: List[Dict[str, Any]] = []
    vals = list((used_by_metric or {}).values())
    if any(bool(getattr(ev, "is_outlier", False)) for ev in vals):
        out.append({"risk_flag": "outlier_present"})
    if any(str(getattr(ev, "qc_status", "") or "") in ("unreviewed", "unknown") for ev in vals):
        out.append({"risk_flag": "qc_uncertainty"})
    return out


def decision_state_from_gate_statuses(
    *,
    gates: Iterable[Any],
    required_gate_keys: Iterable[str],
    blockers: List[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """Pure deterministic decision-state helper shared by templates."""

    req = [str(k) for k in required_gate_keys if str(k).strip()]
    gate_map = {str(getattr(g, "gate_key", "") or ""): g for g in (gates or [])}
    required_pass = all((k in gate_map and str(getattr(gate_map[k], "status", "") or "") == "pass") for k in req)
    decision_state = "ready" if required_pass and not (blockers or []) else "not_ready"
    return decision_state, {"required_gate_keys": req, "required_pass": bool(required_pass)}


def material_readiness_rationale(*, status: str, use_thresholds: bool) -> str:
    """Deterministic rationale text for material readiness gates."""
    st = str(status or "")
    if st == "pass" and use_thresholds:
        return "At least one material readiness metric present and within policy limits."
    if st == "pass":
        return "At least one material readiness metric present."
    return "Missing or out-of-range material readiness metrics."


def mechanism_readiness_rationale(*, gate_key: str, status: str, use_thresholds: bool) -> str:
    """Deterministic rationale text for mechanism readiness gates."""
    gk = str(gate_key or "")
    st = str(status or "")
    if gk == "G4_functional":
        if st == "pass" and use_thresholds:
            return "Functional evidence present and within policy limits."
        if st == "pass":
            return "Functional evidence present."
        return "Missing or out-of-range functional evidence."
    if gk == "G5_internalization_if_kd_present":
        if st == "pass":
            return "Internalization/surface expression present when kd_nM present."
        return "kd_nM present but internalization evidence missing."
    return "Gate evaluated from policy."


def comparability_qc_coherence_summary(*, comparability: Dict[str, Any] | None) -> Dict[str, int]:
    """Pure deterministic extraction of comparability QC coherence summary counts."""
    comp = comparability if isinstance(comparability, dict) else {}
    summ = comp.get("summary") if isinstance(comp.get("summary"), dict) else {}
    try:
        high_ct = int(summ.get("high_severity_count") or 0)
    except Exception:
        high_ct = 0
    try:
        total_ct = int(summ.get("total_flags") or 0)
    except Exception:
        total_ct = 0
    return {"high_severity_count": int(high_ct), "total_flags": int(total_ct)}


def reproducibility_signal_from_soe(
    *,
    required_metric_keys: Iterable[str],
    evidence_summary: list[Dict[str, Any]] | None,
) -> Dict[str, Any]:
    """Pure deterministic reproducibility signal from SoE evidence_summary counts."""
    required_metrics = sorted({str(x).strip() for x in (required_metric_keys or []) if str(x).strip()})
    summary_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(evidence_summary, list):
        for row in evidence_summary:
            if not isinstance(row, dict):
                continue
            mk = str(row.get("metric_key") or "").strip()
            if not mk or mk in summary_map:
                continue
            summary_map[mk] = row

    metrics: List[Dict[str, Any]] = []
    positive_count = 0
    for mk in required_metrics:
        row = summary_map.get(mk) or {}
        try:
            total_count = int(row.get("total_count") or 0)
        except Exception:
            total_count = 0
        try:
            usable_count = int(row.get("usable_count") or 0)
        except Exception:
            usable_count = 0
        is_positive = bool(total_count > 1 and usable_count > 1)
        if is_positive:
            positive_count += 1
        metrics.append(
            {
                "metric_key": mk,
                "total_count": int(total_count),
                "usable_count": int(usable_count),
                "reproducibility_positive": is_positive,
            }
        )

    required_count = len(required_metrics)
    if required_count == 0:
        status = "not_applicable"
    elif not summary_map:
        status = "not_available"
    else:
        status = "available"

    return {
        "status": status,
        "required_metric_count": int(required_count),
        "positive_required_metric_count": int(positive_count),
        "all_required_metrics_positive": bool(required_count > 0 and positive_count == required_count),
        "metrics": metrics,
    }
