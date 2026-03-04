from __future__ import annotations

from psi.core.utils import stable_json_dumps
from psi.services.metric_catalog import (
    load_metric_catalog_v1,
    metric_catalog_entry,
    metric_group_for_key,
    metric_group_sort_key,
    normalize_metric_key,
)


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


def test_metric_catalog_curated_overrides_for_known_metrics() -> None:
    entry = metric_catalog_entry("time_to_onset_days")
    assert entry["label"] == "Time to Onset"
    assert entry["domain"] == "In Vivo"
    assert entry["unit"] == "days"


def test_metric_catalog_aliases_normalize_to_canonical_key() -> None:
    assert normalize_metric_key("hmw_percent") == "hmw_pct"
    assert normalize_metric_key("monomer_percent") == "monomer_pct"
    assert normalize_metric_key("lmw_percent") == "lmw_pct"
    assert normalize_metric_key("expr_yield_mgL") == "titer_mg_l"


def test_metric_group_mapping_for_common_keys_reduces_other_bucket() -> None:
    assert metric_group_for_key("titer_mg_l") == "Expression"
    assert metric_group_for_key("hmw_percent") == "Purity/SEC"
    assert metric_group_for_key("kd_nM") == "Binding"
    assert metric_group_for_key("percent_killing") == "Functional"
    assert metric_group_for_key("value_eu_ml") == "Endotoxin"
    assert metric_group_for_key("cmax_ug_ml") == "PK"
    assert metric_group_for_key("diabetes_incidence_pct") == "In Vivo"


def test_metric_group_sort_key_is_stable() -> None:
    groups = ["Other", "Functional", "Expression", "PK", "Binding", "In Vivo", "Endotoxin", "Purity/SEC"]
    ordered = sorted(groups, key=metric_group_sort_key)
    assert ordered == ["Expression", "Purity/SEC", "Binding", "Functional", "Endotoxin", "PK", "In Vivo", "Other"]


def test_metric_catalog_units_are_conservative_for_variable_unit_metrics() -> None:
    ec50 = metric_catalog_entry("ec50")
    kd = metric_catalog_entry("kd_nM")
    assert ec50["unit"] == ""
    assert kd["unit"] == "nM"
