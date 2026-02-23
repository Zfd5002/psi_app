"""DI Next-Best-Experiment (NBE) planner helpers.

Catalog-driven, deterministic, and policy-visible only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from psi.core.di.catalog import load_catalog


_TIER_ORDER = {"low": 0, "med": 1, "medium": 1, "high": 2}


def _tier_rank(val: str) -> int:
    return _TIER_ORDER.get(str(val or "").strip().lower(), 9)


def _blocker_key(b: Any) -> str:
    if isinstance(b, dict):
        return str(b.get("blocker_key") or "").strip()
    return str(getattr(b, "blocker_key", "") or "").strip()


def _catalog_path_for_ref(*, catalog_id: str, catalog_version: str) -> Path | None:
    if catalog_id == "experiment_catalog_v0_1" and catalog_version == "v0.1":
        return Path(__file__).resolve().parents[2] / "core" / "di" / "catalogs" / "experiment_catalog_v0_1.json"
    return None


def build_experiment_suggestions(
    *,
    blockers: List[Any],
    catalog_id: str,
    catalog_version: str,
    allow_recommended_list: bool = True,
) -> Tuple[Dict[str, List[str]], List[Dict[str, Any]]]:
    """Return (experiment_suggestions, recommended_experiments)."""

    catalog_path = _catalog_path_for_ref(catalog_id=catalog_id, catalog_version=catalog_version)
    if catalog_path is None or not catalog_path.exists():
        return {}, []

    cat = load_catalog(catalog_path)
    experiments = cat.catalog.get("experiments") if isinstance(cat.catalog, dict) else []
    if not isinstance(experiments, list):
        return {}, []

    exp_by_key: Dict[str, Dict[str, Any]] = {}
    for e in experiments:
        if not isinstance(e, dict):
            continue
        ek = str(e.get("experiment_key") or "").strip()
        if ek:
            exp_by_key[ek] = e

    suggestions: Dict[str, List[str]] = {}
    recommended: List[Dict[str, Any]] = []

    for b in blockers or []:
        bk = _blocker_key(b)
        if not bk:
            continue
        matches: List[Dict[str, Any]] = []
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
                recommended.append(
                    {
                        "experiment_key": ek,
                        "name": str(e.get("name") or ""),
                        "resolves": e.get("resolves") if isinstance(e.get("resolves"), list) else [],
                        "outputs": e.get("outputs") if isinstance(e.get("outputs"), list) else [],
                        "prerequisites": e.get("prerequisites") if isinstance(e.get("prerequisites"), list) else [],
                        "time_tier": str(e.get("time_tier") or ""),
                        "cost_tier": str(e.get("cost_tier") or ""),
                        "notes": str(e.get("notes") or ""),
                        "source_blocker": bk,
                    }
                )

    return suggestions, recommended
