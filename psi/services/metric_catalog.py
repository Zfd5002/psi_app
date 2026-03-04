from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from psi.web.ui_labels import humanize_key

_CURATED_METRIC_OVERRIDES: dict[str, dict[str, Any]] = {
    "titer_mg_l": {"label": "Titer", "domain": "Expression", "unit": "mg/L", "sort_order": 120},
    "expr_yield_mgL": {"label": "Expression Yield", "domain": "Expression", "unit": "mg/L", "sort_order": 110},
    "total_yield_mg": {"label": "Total Yield", "domain": "Expression", "unit": "mg", "sort_order": 130},
    "viability_percent": {"label": "Viability", "domain": "Expression", "unit": "%", "sort_order": 140},
    "kd_nM": {"label": "KD", "domain": "Assay", "unit": "nM", "sort_order": 420},
    "percent_killing": {"label": "Percent Killing", "domain": "Assay", "unit": "%", "sort_order": 430},
    "internalization_t1_2_h": {"label": "Internalization t1/2", "domain": "Assay", "unit": "h", "sort_order": 440},
    "surface_expression_pct_24h": {"label": "Surface Expression (24h)", "domain": "Assay", "unit": "%", "sort_order": 450},
    "value_eu_ml": {"label": "Endotoxin Value", "domain": "Endotoxin", "unit": "EU/mL", "sort_order": 340},
    "limit_eu_ml": {"label": "Endotoxin Limit", "domain": "Endotoxin", "unit": "EU/mL", "sort_order": 341},
    "cmax_ug_ml": {"label": "Cmax", "domain": "PK/PD", "unit": "ug/mL", "sort_order": 520},
    "auc": {"label": "AUC", "domain": "PK/PD", "unit": "", "sort_order": 530},
    "half_life_days": {"label": "Half-life", "domain": "PK/PD", "unit": "days", "sort_order": 510},
    "diabetes_incidence_pct": {"label": "Diabetes Incidence", "domain": "In Vivo", "unit": "%", "sort_order": 610},
    "time_to_onset_days": {"label": "Time to Onset", "domain": "In Vivo", "unit": "days", "sort_order": 620},
}


def _catalog_path() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "metric_catalog_v1.json"


@lru_cache(maxsize=1)
def load_metric_catalog_v1() -> dict[str, Any]:
    raw = json.loads(_catalog_path().read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("metric_catalog_load_error")
    metrics = raw.get("metrics")
    if not isinstance(metrics, dict):
        raise ValueError("metric_catalog_load_error")
    normalized_metrics: dict[str, dict[str, Any]] = {}
    for key in sorted(metrics.keys(), key=lambda x: str(x)):
        val = metrics.get(key)
        if not isinstance(val, dict):
            continue
        norm_key = str(key).strip()
        if not norm_key:
            continue
        normalized_metrics[norm_key] = {
            "label": str(val.get("label") or humanize_key(norm_key)),
            "domain": str(val.get("domain") or "Other"),
            "unit": str(val.get("unit") or ""),
            "sort_order": int(val.get("sort_order") or 9999),
            "notes": str(val.get("notes") or ""),
        }
    return {
        "catalog_id": str(raw.get("catalog_id") or "metric_catalog_v1"),
        "catalog_version": str(raw.get("catalog_version") or "v1"),
        "metrics": normalized_metrics,
    }


def metric_catalog_entry(metric_key: str) -> dict[str, Any]:
    key = str(metric_key or "").strip()
    catalog = load_metric_catalog_v1()
    metrics = catalog.get("metrics") if isinstance(catalog.get("metrics"), dict) else {}
    entry = metrics.get(key) if isinstance(metrics.get(key), dict) else None
    if entry is not None:
        return dict(entry)
    curated = _CURATED_METRIC_OVERRIDES.get(key)
    if isinstance(curated, dict):
        return {
            "label": str(curated.get("label") or humanize_key(key)),
            "domain": str(curated.get("domain") or "Other"),
            "unit": str(curated.get("unit") or ""),
            "sort_order": int(curated.get("sort_order") or 9999),
            "notes": str(curated.get("notes") or ""),
        }
    return {
        "label": humanize_key(key),
        "domain": "Other",
        "unit": "",
        "sort_order": 9999,
        "notes": "",
    }


def metric_group_for_key(metric_key: str) -> str:
    """Canonical report grouping for a metric key (catalog-backed with deterministic fallback)."""
    key = str(metric_key or "").strip()
    if not key:
        return "Other"
    entry = metric_catalog_entry(key)
    domain = str(entry.get("domain") or "").strip()
    if domain and domain.lower() != "other":
        return domain
    mk = key.lower()
    if "sec" in mk or "hmw" in mk or "lmw" in mk or "monomer" in mk:
        return "SEC"
    if "sds" in mk or "ce-sds" in mk or "cesds" in mk:
        return "SDS"
    if "dsf" in mk or "tm" in mk:
        return "DSF"
    if "endo" in mk or "lal" in mk:
        return "Endotoxin"
    if "pk" in mk or "pd" in mk:
        return "PK/PD"
    if "ec50" in mk or "ic50" in mk or "potency" in mk or "kd" in mk:
        return "Assay"
    return "Other"
