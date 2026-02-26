from __future__ import annotations

from typing import Any, Dict


def _policy_risk_flag_severity_tiers(*, policy_package: Dict[str, Any] | None, policy_body: Dict[str, Any]) -> Dict[str, str]:
    raw = (policy_body or {}).get("risk_flag_severity_tiers")
    template_structure = (policy_package or {}).get("template_structure") if isinstance(policy_package, dict) else {}
    if not isinstance(template_structure, dict):
        template_structure = {}
    if not isinstance(raw, dict):
        raw = template_structure.get("risk_flag_severity_tiers")
    if not isinstance(raw, dict):
        raw = {}
    out: Dict[str, str] = {}
    for k in sorted([str(x) for x in raw.keys() if str(x).strip()]):
        sev = str(raw.get(k) or "").strip().lower()
        # Legacy compatibility shim: pre-x18 snapshot-referenced policies may still carry
        # `moderate`; forward policy vocabulary is `medium`. Keep this normalization until
        # legacy snapshot replay support is formally retired (documented deprecation horizon).
        if sev == "moderate":
            sev = "medium"
        if sev in ("high", "medium", "low"):
            out[k] = sev
    return out


def derive_risk_flags_enriched(
    *,
    risk_flags: list[Dict[str, Any]],
    used_by_metric: Dict[str, Any],
    policy_body: Dict[str, Any],
    policy_package: Dict[str, Any] | None = None,
) -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    used_keys = set(str(k) for k in (used_by_metric or {}).keys())
    severity_tiers = _policy_risk_flag_severity_tiers(policy_package=policy_package, policy_body=policy_body)

    for rf in risk_flags or []:
        key = str((rf or {}).get("risk_flag") or (rf or {}).get("key") or "").strip()
        if not key:
            continue

        category = "other"
        severity = str(severity_tiers.get(key) or "unspecified")
        related_metrics: list[str] = []
        explanation = str((rf or {}).get("detail") or (rf or {}).get("explanation") or key)

        if key in ("qc_uncertainty", "outlier_present"):
            category = "data_quality"
        elif key in ("interpretation_gap", "context_missing"):
            category = "interpretation"
        elif key in ("method_incomparable",):
            category = "comparability"
        elif key in ("coverage_gap", "missing_required_metric"):
            category = "coverage"

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

    # Keep legacy `moderate` rank-equivalent to `medium` for deterministic ordering.
    sev_rank = {"high": 0, "medium": 1, "moderate": 1, "low": 2, "unspecified": 3}
    out = sorted(out, key=lambda x: (sev_rank.get(str((x or {}).get("severity") or "").strip().lower(), 9), str((x or {}).get("category") or ""), str((x or {}).get("key") or "")))
    return out
