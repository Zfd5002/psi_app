from __future__ import annotations

from typing import Any, Dict


def derive_risk_flags_enriched(*, risk_flags: list[Dict[str, Any]], used_by_metric: Dict[str, Any], policy_body: Dict[str, Any]) -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    used_keys = set(str(k) for k in (used_by_metric or {}).keys())

    for rf in risk_flags or []:
        key = str((rf or {}).get("risk_flag") or (rf or {}).get("key") or "").strip()
        if not key:
            continue

        category = "other"
        severity = "low"
        related_metrics: list[str] = []
        explanation = str((rf or {}).get("detail") or (rf or {}).get("explanation") or key)

        if key in ("qc_uncertainty", "outlier_present"):
            category = "data_quality"
            severity = "moderate"
        elif key in ("interpretation_gap", "context_missing"):
            category = "interpretation"
            severity = "high"
        elif key in ("method_incomparable",):
            category = "comparability"
            severity = "moderate"
        elif key in ("coverage_gap", "missing_required_metric"):
            category = "coverage"
            severity = "high"

        gates = (policy_body or {}).get("gates") or {}
        if isinstance(gates, dict):
            for gd in gates.values():
                if not isinstance(gd, dict):
                    continue
                lst = gd.get("require_all") if isinstance(gd.get("require_all"), list) else gd.get("require_any")
                if isinstance(lst, list):
                    for x in lst:
                        sx = str(x).strip()
                        if sx and sx in used_keys:
                            related_metrics.append(sx)
        related_metrics = sorted(set(related_metrics))

        out.append(
            {
                "key": key,
                "category": category,
                "severity": severity,
                "related_metrics": related_metrics,
                "explanation": explanation,
            }
        )

    sev_rank = {"high": 0, "moderate": 1, "low": 2}
    out = sorted(out, key=lambda x: (sev_rank.get(str((x or {}).get("severity") or "").strip().lower(), 9), str((x or {}).get("category") or ""), str((x or {}).get("key") or "")))
    return out
