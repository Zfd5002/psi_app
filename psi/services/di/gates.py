from __future__ import annotations

from typing import Any, Dict, List

from psi.core.di.schema import EvidenceRef


def _metric_ok(metric_evaluations: Dict[str, Any], metric_key: str, *, enforce: bool) -> bool:
    if not enforce:
        return True
    ev = metric_evaluations.get(metric_key) if isinstance(metric_evaluations, dict) else None
    if not isinstance(ev, dict):
        return True
    status = str(ev.get("evaluated_status") or "").strip().upper()
    if not status:
        return True
    return status in ("PASS", "WARN", "INFO")


def _require_any(
    used: Dict[str, EvidenceRef],
    keys: List[str],
    metric_evaluations: Dict[str, Any],
    *,
    enforce_value_functions: bool,
) -> Dict[str, Any]:
    ok_present = [k for k in keys if k in used and _metric_ok(metric_evaluations, k, enforce=enforce_value_functions)]
    failed_present = [k for k in keys if k in used and not _metric_ok(metric_evaluations, k, enforce=enforce_value_functions)]
    evidence_refs = [used[k] for k in keys if k in used]
    return {
        "ok": len(ok_present) > 0,
        "evidence_refs": evidence_refs,
        "missing_any_of": list(keys),
        "failed_metrics": failed_present,
    }


def _require_all(
    used: Dict[str, EvidenceRef],
    keys: List[str],
    metric_evaluations: Dict[str, Any],
    *,
    enforce_value_functions: bool,
) -> Dict[str, Any]:
    missing = [k for k in keys if k not in used]
    failed = [k for k in keys if k in used and not _metric_ok(metric_evaluations, k, enforce=enforce_value_functions)]
    evidence_refs = [used[k] for k in keys if k in used]
    return {
        "ok": (len(missing) == 0 and len(failed) == 0),
        "evidence_refs": evidence_refs,
        "missing": missing,
        "failed_metrics": failed,
    }


def evaluate_gates(
    *,
    policy_body: Dict[str, Any],
    gate_keys: List[str],
    used_by_metric: Dict[str, EvidenceRef],
    metric_evaluations: Dict[str, Any],
    enforce_value_functions: bool,
    context: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Policy-driven gate evaluation for deterministic templates."""
    gates_cfg = (policy_body or {}).get("gates") if isinstance(policy_body, dict) else {}
    if not isinstance(gates_cfg, dict):
        return []
    ctx = context or {}

    out: List[Dict[str, Any]] = []
    for gate_key in gate_keys:
        gd = gates_cfg.get(gate_key) if isinstance(gates_cfg, dict) else None
        if not isinstance(gd, dict):
            continue
        if gd.get("enabled") is False:
            continue

        knob = str(gd.get("context_knob") or "").strip()
        if knob and not ctx.get(knob):
            continue

        if_present = gd.get("if_present") if isinstance(gd.get("if_present"), list) else []
        if if_present:
            if not any(str(k) in used_by_metric for k in if_present):
                continue

        require_all = gd.get("require_all") if isinstance(gd.get("require_all"), list) else []
        require_any = gd.get("require_any") if isinstance(gd.get("require_any"), list) else []

        if require_all:
            res = _require_all(
                used_by_metric,
                [str(k) for k in require_all],
                metric_evaluations,
                enforce_value_functions=enforce_value_functions,
            )
        elif require_any:
            res = _require_any(
                used_by_metric,
                [str(k) for k in require_any],
                metric_evaluations,
                enforce_value_functions=enforce_value_functions,
            )
        else:
            continue

        out.append(
            {
                "gate_key": gate_key,
                "status": "pass" if res.get("ok") else "fail",
                "evidence_refs": res.get("evidence_refs") or [],
                "missing": res.get("missing") or [],
                "missing_any_of": res.get("missing_any_of") or [],
                "failed_metrics": res.get("failed_metrics") or [],
            }
        )

    return out
