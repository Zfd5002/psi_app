from __future__ import annotations

from typing import Any, Dict


def coverage_fingerprint_payload(*, readiness: Dict[str, Any], gate_outcomes: Dict[str, Any]) -> Dict[str, Any]:
    r = readiness or {}
    cov = (r.get("coverage") or {}) if isinstance(r, dict) else {}
    comp = (r.get("comparability") or {}) if isinstance(r, dict) else {}
    return {
        "blockers": r.get("blockers") or [],
        "coverage": {
            "required_present": cov.get("required_present"),
            "required_total": cov.get("required_total"),
            "optional_present": cov.get("optional_present"),
            "optional_total": cov.get("optional_total"),
            "coverage_ratio": cov.get("coverage_ratio"),
        },
        "gate_outcomes": gate_outcomes or {},
        "comparability": {
            "method_incomparable_metrics": (comp.get("method_incomparable_metrics") or []),
            "notes": (comp.get("notes") or []),
        },
    }


def derive_suggestions(
    *,
    gate_outcomes: Dict[str, Any],
    readiness: Dict[str, Any],
    ignored: list[Any],
) -> list[Dict[str, Any]]:
    """Policy-derived, non-ranked suggestions.

    Derived only from missing evidence and ignore taxonomy.
    """

    suggestions: Dict[str, Dict[str, Any]] = {}

    # Missing metrics from gate_outcomes
    for gk, gi in (gate_outcomes or {}).items():
        _ = gk
        miss = (gi or {}).get("missing_metrics") or []
        if isinstance(miss, list):
            for mk in miss:
                smk = str(mk).strip()
                if not smk:
                    continue
                sid = f"missing_metric:{smk}"
                suggestions[sid] = {
                    "suggestion_id": sid,
                    "type": "missing_metric",
                    "rationale": "Metric required by policy but missing in selected evidence.",
                    "action_spec": {"metric_key": smk, "preferred_method": None, "required_unit": None},
                }

    # Method incomparability (from readiness.comparability)
    comp = (readiness or {}).get("comparability") or {}
    mi = comp.get("method_incomparable_metrics") if isinstance(comp, dict) else []
    if isinstance(mi, list):
        for mk in mi:
            smk = str(mk).strip()
            if not smk:
                continue
            sid = f"method_incomparable:{smk}"
            suggestions[sid] = {
                "suggestion_id": sid,
                "type": "method_incomparable",
                "rationale": "Evidence exists but is method-incomparable under policy; capture comparable method per SOP.",
                "action_spec": {"metric_key": smk, "preferred_method": None, "required_unit": None},
            }

    # Unit incompatibility (from ignored taxonomy)
    for ig in ignored or []:
        try:
            rk = str(getattr(ig, "reason_key", "") or "").strip()
            mk = str(getattr(ig, "metric_key", "") or "").strip()
        except Exception:
            rk, mk = "", ""
        if not mk:
            continue
        if rk == "unit_inconvertible":
            sid = f"unit_inconvertible:{mk}"
            suggestions[sid] = {
                "suggestion_id": sid,
                "type": "unit_inconvertible",
                "rationale": "Evidence exists but unit is not comparable/convertible under current policy constraints.",
                "action_spec": {"metric_key": mk, "preferred_method": None, "required_unit": None},
            }

    return [suggestions[k] for k in sorted(suggestions.keys())]
