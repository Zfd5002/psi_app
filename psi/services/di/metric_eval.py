from __future__ import annotations

from typing import Any, Dict


def derive_metric_evaluations(
    *,
    policy_body: Dict[str, Any],
    used_by_metric: Dict[str, Any],
    context: Dict[str, Any] | None = None,
) -> tuple[Dict[str, Dict[str, Any]], list[Dict[str, Any]]]:
    """Policy-visible, deterministic value-function evaluation per metric.

    Returns: (metric_evaluations, interpretation_gap_flags)
    """
    defs = (policy_body or {}).get("metric_value_functions") or {}
    if not isinstance(defs, dict):
        return {}, []

    used_keys = set(str(k) for k in (used_by_metric or {}).keys())
    ctx = context or {}

    evals: Dict[str, Dict[str, Any]] = {}
    gap_flags: list[Dict[str, Any]] = []

    for mk in sorted([str(k) for k in defs.keys()]):
        vf = defs.get(mk) or {}
        if not isinstance(vf, dict):
            continue
        vf_type = str(vf.get("type") or "").strip()
        if not vf_type:
            continue

        companion = vf.get("companion_requirements") if isinstance(vf.get("companion_requirements"), list) else []
        companion = sorted({str(x).strip() for x in companion if str(x).strip()})
        missing_companion = sorted([x for x in companion if x not in used_keys])

        interpretation_gap = False
        reasons: list[Dict[str, Any]] = []
        if missing_companion:
            interpretation_gap = True
            reasons.append({"kind": "missing_companion", "missing": missing_companion})

        if vf_type == "context_dependent":
            ctx_key = str(vf.get("context_key") or "").strip()
            if ctx_key and not ctx.get(ctx_key):
                interpretation_gap = True
                reasons.append({"kind": "missing_context", "context_key": ctx_key})

        ev = used_by_metric.get(mk)
        value_num = None
        if ev is not None:
            value_num = ev.get("value_num") if isinstance(ev, dict) else getattr(ev, "value_num", None)

        status = "UNKNOWN"
        if vf_type == "informational_only":
            status = "INFO"
        elif interpretation_gap:
            status = "UNKNOWN"
        elif value_num is None:
            reasons.append({"kind": "missing_value_num"})
            status = "UNKNOWN"
        else:
            try:
                v = float(value_num)
            except Exception:
                v = None
                reasons.append({"kind": "non_numeric_value"})
                status = "UNKNOWN"

            if v is not None:
                if vf_type == "maximize":
                    min_value = vf.get("min_value")
                    if min_value is None:
                        reasons.append({"kind": "missing_min_value"})
                    else:
                        status = "PASS" if v >= float(min_value) else "FAIL"
                elif vf_type == "minimize":
                    max_value = vf.get("max_value")
                    if max_value is None:
                        reasons.append({"kind": "missing_max_value"})
                    else:
                        status = "PASS" if v <= float(max_value) else "FAIL"
                elif vf_type == "hard_cap":
                    cap_value = vf.get("cap_value")
                    if cap_value is None:
                        reasons.append({"kind": "missing_cap_value"})
                    else:
                        status = "PASS" if v <= float(cap_value) else "FAIL"
                elif vf_type == "optimal_window":
                    min_value = vf.get("min_value")
                    max_value = vf.get("max_value")
                    if min_value is None or max_value is None:
                        reasons.append({"kind": "missing_window"})
                    else:
                        status = "PASS" if float(min_value) <= v <= float(max_value) else "FAIL"
                elif vf_type == "risk_zone":
                    min_value = vf.get("min_value")
                    max_value = vf.get("max_value")
                    risk_if = str(vf.get("risk_if") or "inside").strip().lower()
                    if min_value is None or max_value is None:
                        reasons.append({"kind": "missing_risk_bounds"})
                    else:
                        inside = float(min_value) <= v <= float(max_value)
                        warn = inside if risk_if != "outside" else not inside
                        status = "WARN" if warn else "PASS"
                elif vf_type == "context_dependent":
                    status = "INFO"
                else:
                    reasons.append({"kind": "unknown_value_function"})

        evals[mk] = {
            "metric_key": mk,
            "applied_value_function_type": vf_type,
            "evaluated_status": status,
            "interpretation_gap": bool(interpretation_gap),
            "reasons": reasons,
        }

        if interpretation_gap:
            gap_flags.append(
                {
                    "risk_flag": "interpretation_gap",
                    "metric_key": mk,
                    "missing_requirements": missing_companion,
                    "detail": {"value_function_type": vf_type},
                }
            )

    return evals, gap_flags
