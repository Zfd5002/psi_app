from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from psi.web.ui_labels import humanize_key


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
    return {
        "label": humanize_key(key),
        "domain": "Other",
        "unit": "",
        "sort_order": 9999,
        "notes": "",
    }
