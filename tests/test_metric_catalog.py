from __future__ import annotations

from psi.core.utils import stable_json_dumps
from psi.services.metric_catalog import load_metric_catalog_v1, metric_catalog_entry


def test_metric_catalog_loader_is_deterministic() -> None:
    a = load_metric_catalog_v1()
    b = load_metric_catalog_v1()
    assert stable_json_dumps(a) == stable_json_dumps(b)
    assert str(a.get("catalog_id") or "") == "metric_catalog_v1"
    metrics = a.get("metrics") if isinstance(a.get("metrics"), dict) else {}
    assert list(metrics.keys()) == sorted(list(metrics.keys()))


def test_metric_catalog_entry_fallback_is_stable() -> None:
    entry = metric_catalog_entry("unknown_metric_key")
    assert entry == {
        "label": "Unknown Metric Key",
        "domain": "Other",
        "unit": "",
        "sort_order": 9999,
        "notes": "",
    }
