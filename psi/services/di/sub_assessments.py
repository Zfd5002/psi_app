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

