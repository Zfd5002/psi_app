"""DI Next-Best-Experiment (NBE) planner helpers.

Catalog-driven, deterministic, and policy-visible only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from psi.core.di.catalog import load_experiment_catalog_v0_1


_TIER_ORDER = {"low": 0, "med": 1, "medium": 1, "high": 2}


def _tier_rank(val: str) -> int:
    return _TIER_ORDER.get(str(val or "").strip().lower(), 9)


def _blocker_key(b: Any) -> str:
    if isinstance(b, dict):
        return str(b.get("blocker_key") or "").strip()
    return str(getattr(b, "blocker_key", "") or "").strip()


def _load_catalog_for_ref(*, catalog_id: str, catalog_version: str):
    if catalog_id == "experiment_catalog_v0_1" and catalog_version == "v0.1":
        return load_experiment_catalog_v0_1()
    return None


def _metric_keys_from_experiment(e: Dict[str, Any]) -> list[str]:
    keys = e.get("metric_keys") if isinstance(e.get("metric_keys"), list) else []
    return sorted({str(x).strip() for x in keys if str(x).strip()})


def _missing_metrics_from_blocker(b: Any) -> list[str]:
    if not isinstance(b, dict):
        return []
    detail = b.get("detail") if isinstance(b.get("detail"), dict) else {}
    missing = detail.get("missing") if isinstance(detail.get("missing"), list) else []
    missing_any = detail.get("missing_any_of") if isinstance(detail.get("missing_any_of"), list) else []
    out = [str(x).strip() for x in (missing + missing_any) if str(x).strip()]
    return sorted(set(out))


def _risk_flag_key(r: Any) -> str:
    if isinstance(r, dict):
        for k in ("risk_key", "risk_flag", "key"):
            v = str(r.get(k) or "").strip()
            if v:
                return v
        return ""
    for k in ("risk_key", "risk_flag", "key"):
        v = str(getattr(r, k, "") or "").strip()
        if v:
            return v
    return ""


# Deterministic, policy-visible NBE extension (w61): risk flags may trigger suggestions.
# Keyed only by explicit flag names; no scoring or hidden ranking.
_RISK_FLAG_TO_EXPERIMENT_KEYS: Dict[str, List[str]] = {
    "aggregated_purity_interpretation_gap": ["run_sec_hplc", "repeat_assay_or_review_qc"],
    "interpretation_gap": ["run_functional_assay", "run_sec_hplc"],
}


def build_experiment_suggestions(
    *,
    blockers: List[Any],
    risk_flags: List[Any] | None = None,
    catalog_id: str,
    catalog_version: str,
    allow_recommended_list: bool = True,
) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    """Return (experiment_suggestions, recommended_experiments)."""

    cat = _load_catalog_for_ref(catalog_id=catalog_id, catalog_version=catalog_version)
    if cat is None:
        return {}, []

    experiments = cat.catalog.get("experiments") if isinstance(cat.catalog, dict) else []
    if not isinstance(experiments, list):
        return {}, []

    exp_by_key: Dict[str, Dict[str, Any]] = {}
    metrics_by_exp: Dict[str, List[str]] = {}
    for e in experiments:
        if not isinstance(e, dict):
            continue
        ek = str(e.get("experiment_key") or "").strip()
        if ek:
            exp_by_key[ek] = e
            metrics_by_exp[ek] = _metric_keys_from_experiment(e)

    suggestions: Dict[str, List[str]] = {}
    recommended_map: Dict[str, Dict[str, Any]] = {}

    for b in blockers or []:
        bk = _blocker_key(b)
        if not bk:
            continue
        matches: List[Dict[str, Any]] = []
        missing_metrics = _missing_metrics_from_blocker(b) if bk == "missing_required_metric" else []

        for ek, e in exp_by_key.items():
            resolves = e.get("resolves") if isinstance(e.get("resolves"), list) else []
            resolves = [str(x).strip() for x in resolves if str(x).strip()]
            if missing_metrics:
                if any(m in (metrics_by_exp.get(ek) or []) for m in missing_metrics):
                    matches.append(e)
            else:
                if bk in resolves:
                    matches.append(e)

        if missing_metrics and not matches:
            for e in exp_by_key.values():
                resolves = e.get("resolves") if isinstance(e.get("resolves"), list) else []
                if bk in [str(x).strip() for x in resolves if str(x).strip()]:
                    matches.append(e)

        matches.sort(
            key=lambda e: (
                _tier_rank(e.get("time_tier")),
                _tier_rank(e.get("cost_tier")),
                str(e.get("experiment_key") or ""),
            )
        )

        keys = [str(e.get("experiment_key") or "") for e in matches if str(e.get("experiment_key") or "")]
        if keys:
            suggestions[bk] = keys

        if allow_recommended_list:
            for e in matches:
                ek = str(e.get("experiment_key") or "")
                if not ek:
                    continue
                entry = recommended_map.get(ek)
                if entry is None:
                    entry = {
                        "experiment_key": ek,
                        "name": str(e.get("name") or ""),
                        "resolves": [],
                        "outputs": [],
                        "metric_keys": [],
                        "prerequisites": [],
                        "time_tier": str(e.get("time_tier") or ""),
                        "cost_tier": str(e.get("cost_tier") or ""),
                        "notes": str(e.get("notes") or ""),
                        "triggered_by_blockers": [],
                        "triggered_by_risk_flags": [],
                    }
                    recommended_map[ek] = entry

                entry["triggered_by_blockers"] = sorted(
                    list(set((entry.get("triggered_by_blockers") or []) + [bk]))
                )

                resolves = e.get("resolves") if isinstance(e.get("resolves"), list) else []
                entry["resolves"] = sorted(list(set((entry.get("resolves") or []) + resolves)))

                outputs = e.get("outputs") if isinstance(e.get("outputs"), list) else []
                entry["outputs"] = sorted(list(set((entry.get("outputs") or []) + outputs)))

                prereq = e.get("prerequisites") if isinstance(e.get("prerequisites"), list) else []
                entry["prerequisites"] = sorted(list(set((entry.get("prerequisites") or []) + prereq)))

                entry["metric_keys"] = sorted(list(set((entry.get("metric_keys") or []) + (metrics_by_exp.get(ek) or []))))

    for rf in sorted({_risk_flag_key(r) for r in (risk_flags or []) if _risk_flag_key(r)}):
        mapped_keys = [str(x).strip() for x in (_RISK_FLAG_TO_EXPERIMENT_KEYS.get(rf) or []) if str(x).strip()]
        if not mapped_keys:
            continue
        matches = [exp_by_key[ek] for ek in mapped_keys if ek in exp_by_key]
        matches.sort(
            key=lambda e: (
                _tier_rank(e.get("time_tier")),
                _tier_rank(e.get("cost_tier")),
                str(e.get("experiment_key") or ""),
            )
        )
        keys = [str(e.get("experiment_key") or "") for e in matches if str(e.get("experiment_key") or "")]
        if not keys:
            continue
        suggestions[f"risk_flag:{rf}"] = keys
        if allow_recommended_list:
            for e in matches:
                ek = str(e.get("experiment_key") or "")
                if not ek:
                    continue
                entry = recommended_map.get(ek)
                if entry is None:
                    entry = {
                        "experiment_key": ek,
                        "name": str(e.get("name") or ""),
                        "resolves": [],
                        "outputs": [],
                        "metric_keys": [],
                        "prerequisites": [],
                        "time_tier": str(e.get("time_tier") or ""),
                        "cost_tier": str(e.get("cost_tier") or ""),
                        "notes": str(e.get("notes") or ""),
                        "triggered_by_blockers": [],
                        "triggered_by_risk_flags": [],
                    }
                    recommended_map[ek] = entry
                entry["triggered_by_risk_flags"] = sorted(
                    list(set((entry.get("triggered_by_risk_flags") or []) + [rf]))
                )
                resolves = e.get("resolves") if isinstance(e.get("resolves"), list) else []
                entry["resolves"] = sorted(list(set((entry.get("resolves") or []) + resolves)))
                outputs = e.get("outputs") if isinstance(e.get("outputs"), list) else []
                entry["outputs"] = sorted(list(set((entry.get("outputs") or []) + outputs)))
                prereq = e.get("prerequisites") if isinstance(e.get("prerequisites"), list) else []
                entry["prerequisites"] = sorted(list(set((entry.get("prerequisites") or []) + prereq)))
                entry["metric_keys"] = sorted(list(set((entry.get("metric_keys") or []) + (metrics_by_exp.get(ek) or []))))

    recommended = sorted(
        list(recommended_map.values()),
        key=lambda e: (
            _tier_rank(e.get("time_tier")),
            _tier_rank(e.get("cost_tier")),
            str(e.get("experiment_key") or ""),
        ),
    )

    return suggestions, recommended
