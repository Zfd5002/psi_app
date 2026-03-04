from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_cols
from psi.core.di.catalog import load_template_prerequisites_latest
from psi.services.metric_catalog import metric_catalog_entry, metric_group_for_key, metric_group_sort_key, normalize_metric_key

_STABILITY_MIN_BATCHES_WITH_REQUIRED = 2
_STABILITY_MAX_REGRESSION_REQUIRED_PRESENT = 2

# Canonical display order for molecule fact-sheet metrics.
# Contract: render known discovery-stage metrics in this sequence,
# then render any remaining observed metrics alphabetically.
_CANONICAL_METRIC_STAGE_ORDER: list[str] = [
    "expr_yield_mgL",
    "titer_mg_l",
    "titer_g_l",
    "total_yield_mg",
    "viability_percent",
    "purity_percent",
    "purity_pct",
    "monomer_pct",
    "monomer_percent",
    "hmw_pct",
    "hmw_percent",
    "lmw_pct",
    "lmw_percent",
    "aggregation_pct",
    "value_eu_ml",
    "limit_eu_ml",
    "percent_killing",
    "ec50",
    "kd_nM",
    "internalization_t1_2_h",
    "surface_expression_pct_24h",
    "half_life_days",
    "auc",
    "cmax_ug_ml",
    "diabetes_incidence_pct",
    "time_to_onset_days",
]
_CANONICAL_METRIC_ORDER_INDEX = {
    key: idx for idx, key in enumerate(_CANONICAL_METRIC_STAGE_ORDER)
}
_SUFFIX_UNIT_FALLBACKS: dict[str, str] = {
    "_pct": "%",
    "_percent": "%",
    "_mg_l": "mg/L",
    "_g_l": "g/L",
    "_eu_ml": "EU/mL",
    "_nm": "nM",
    "_ug_ml": "ug/mL",
    "_days": "days",
    "_h": "h",
}


def _norm_str(v: object) -> str:
    return str(v or "").strip()


def _fallback_unit_for_metric_key(metric_key: str) -> str:
    mk = _norm_str(metric_key).lower()
    if not mk:
        return ""
    for suffix, unit in sorted(_SUFFIX_UNIT_FALLBACKS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if mk.endswith(suffix):
            return unit
    return ""


def _display_value(*, value_num: object, value_text: object, unit: object, metric_key: str) -> str:
    if value_num is not None and _norm_str(value_num):
        u = _norm_str(unit)
        if not u:
            u = _norm_str(metric_catalog_entry(metric_key).get("unit"))
        if not u:
            u = _fallback_unit_for_metric_key(metric_key)
        return f"{value_num}{(' ' + u) if u else ''}".strip()
    txt = _norm_str(value_text)
    if txt:
        return txt
    return "not run"


def _is_qc_failed(*, qc_value: object, ignore_for_model: object) -> bool:
    if str(ignore_for_model or "").strip() in {"1", "true", "True"}:
        return True
    q = _norm_str(qc_value).lower()
    return q in {"rejected", "reject", "failed", "fail", "qc_failed"}


def _ordered_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        s = _norm_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _parse_iso_epoch(value: str) -> float | None:
    txt = _norm_str(value)
    if not txt:
        return None
    try:
        return float(datetime.fromisoformat(txt).timestamp())
    except Exception:
        return None


def _resolve_required_metric_keys(*, template_ids_used: list[str], snapshot_output: dict[str, Any]) -> list[str]:
    # Canonical prerequisites loader usage is explicit and deterministic for template-id normalization.
    prereq_pol = load_template_prerequisites_latest().policy
    prereq_map = prereq_pol.get("template_prerequisites") if isinstance(prereq_pol.get("template_prerequisites"), dict) else {}
    available_templates = sorted(str(k) for k in prereq_map.keys())
    resolved_template_ids: list[str] = []
    for tid in _ordered_unique(template_ids_used):
        exact = [k for k in available_templates if k == tid]
        prefix = [k for k in available_templates if k.startswith(f"{tid}.")]
        for k in sorted(exact + prefix):
            if k not in resolved_template_ids:
                resolved_template_ids.append(k)
    gates = snapshot_output.get("gates") if isinstance(snapshot_output.get("gates"), list) else []
    required: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        for key in ("required_metrics", "required_metrics_base"):
            vals = gate.get(key) if isinstance(gate.get(key), list) else []
            for mk in vals:
                s = normalize_metric_key(_norm_str(mk))
                if s:
                    required.add(s)
    return sorted(required)


def _ordered_metric_keys(
    *,
    observed_metric_keys: set[str],
    required_metric_keys: list[str],
    preserve_required_priority: bool,
) -> list[str]:
    observed = sorted({_norm_str(k) for k in observed_metric_keys if _norm_str(k)})
    if not observed:
        return []
    required = [_norm_str(k) for k in required_metric_keys if _norm_str(k)]
    required_unique = _ordered_unique(required)
    seen: set[str] = set()
    out: list[str] = []
    if preserve_required_priority:
        for mk in required_unique:
            if mk in observed and mk not in seen:
                seen.add(mk)
                out.append(mk)
    remaining = [mk for mk in observed if mk not in seen]
    ordered_remaining = sorted(
        remaining,
        key=lambda mk: (
            _CANONICAL_METRIC_ORDER_INDEX.get(mk, 10_000),
            mk,
        ),
    )
    out.extend(ordered_remaining)
    return out


def _compute_best_batch(
    *,
    required_present_by_batch: list[dict[str, Any]],
    batch_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_by_id: dict[int | None, dict[str, Any]] = {}
    for row in batch_registry:
        if not isinstance(row, dict):
            continue
        registry_by_id[row.get("batch_id")] = row

    candidates: list[dict[str, Any]] = []
    for row in required_present_by_batch:
        if not isinstance(row, dict):
            continue
        batch_id = row.get("batch_id")
        registry = registry_by_id.get(batch_id, {})
        batch_date = _norm_str(registry.get("batch_date"))
        recency_ts = _parse_iso_epoch(batch_date)
        batch_id_num = int(batch_id) if isinstance(batch_id, int) else -1
        recency_score = recency_ts if recency_ts is not None else float(batch_id_num)
        score = (
            int(row.get("required_present_count") or 0),
            int(row.get("total_present_count") or 0),
            recency_score,
            batch_id_num,
        )
        candidates.append(
            {
                "batch_id": batch_id,
                "batch_label": str(row.get("batch_label") or ""),
                "required_present_count": int(row.get("required_present_count") or 0),
                "total_present_count": int(row.get("total_present_count") or 0),
                "recency_basis": ("created_at" if recency_ts is not None else "batch_id"),
                "batch_date": batch_date,
                "score": score,
            }
        )

    candidates_sorted = sorted(
        candidates,
        key=lambda c: (
            int(c.get("required_present_count") or 0),
            int(c.get("total_present_count") or 0),
            float(c.get("score", (0, 0, 0.0, -1))[2]),
            int(c.get("score", (0, 0, 0.0, -1))[3]),
        ),
        reverse=True,
    )
    trace = [
        {
            "batch_id": c.get("batch_id"),
            "batch_label": c.get("batch_label"),
            "required_present_count": int(c.get("required_present_count") or 0),
            "total_present_count": int(c.get("total_present_count") or 0),
            "recency_basis": str(c.get("recency_basis") or ""),
            "batch_date": str(c.get("batch_date") or ""),
            "score": [
                int(c.get("required_present_count") or 0),
                int(c.get("total_present_count") or 0),
                float(c.get("score", (0, 0, 0.0, -1))[2]),
                int(c.get("score", (0, 0, 0.0, -1))[3]),
            ],
        }
        for c in candidates_sorted
    ]
    selected_batch_id = trace[0].get("batch_id") if trace else None
    return {
        "status": "computed",
        "selection_method": "coverage_score_v1",
        "selected_batch_id": selected_batch_id,
        "trace": trace,
    }


def _compute_stability(
    *,
    required_present_by_batch: list[dict[str, Any]],
    best_batch: dict[str, Any],
    batch_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    registry_by_id = {
        row.get("batch_id"): row
        for row in batch_registry
        if isinstance(row, dict)
    }
    rows: list[dict[str, Any]] = []
    for row in required_present_by_batch:
        if not isinstance(row, dict):
            continue
        batch_id = row.get("batch_id")
        reg = registry_by_id.get(batch_id, {})
        date_txt = _norm_str(reg.get("batch_date"))
        recency_ts = _parse_iso_epoch(date_txt)
        batch_id_num = int(batch_id) if isinstance(batch_id, int) else -1
        rows.append(
            {
                "batch_id": batch_id,
                "required_present_count": int(row.get("required_present_count") or 0),
                "batch_date": date_txt,
                "recency_score": (recency_ts if recency_ts is not None else float(batch_id_num)),
            }
        )
    rows_sorted = sorted(
        rows,
        key=lambda r: (
            float(r.get("recency_score") or -1.0),
            int(r.get("batch_id") if isinstance(r.get("batch_id"), int) else -1),
        ),
        reverse=True,
    )
    with_required = [r for r in rows_sorted if int(r.get("required_present_count") or 0) > 0]
    if len(with_required) < _STABILITY_MIN_BATCHES_WITH_REQUIRED:
        return {
            "status": "insufficient_data",
            "method": "coverage_only_v1",
            "rationale": [
                f"insufficient_batches_with_required_coverage: {len(with_required)} < {_STABILITY_MIN_BATCHES_WITH_REQUIRED}",
            ],
        }

    selected_batch_id = best_batch.get("selected_batch_id") if isinstance(best_batch, dict) else None
    selected = next((r for r in rows_sorted if r.get("batch_id") == selected_batch_id), None)
    if selected is None:
        return {
            "status": "insufficient_data",
            "method": "coverage_only_v1",
            "rationale": ["best_batch_not_found_in_registry"],
        }

    best_required = int(selected.get("required_present_count") or 0)
    best_recency = float(selected.get("recency_score") or -1.0)
    regressions: list[dict[str, Any]] = []
    for row in rows_sorted:
        if float(row.get("recency_score") or -1.0) <= best_recency:
            continue
        required_present = int(row.get("required_present_count") or 0)
        if required_present <= (best_required - _STABILITY_MAX_REGRESSION_REQUIRED_PRESENT):
            regressions.append(row)
    if regressions:
        regressions_sorted = sorted(
            regressions,
            key=lambda r: (
                float(r.get("recency_score") or -1.0),
                int(r.get("batch_id") if isinstance(r.get("batch_id"), int) else -1),
            ),
            reverse=True,
        )
        rationale = [
            f"regression_detected batch_id={r.get('batch_id')} required_present={int(r.get('required_present_count') or 0)} best_required={best_required}"
            for r in regressions_sorted
        ]
        return {
            "status": "unstable",
            "method": "coverage_only_v1",
            "rationale": rationale,
        }
    return {
        "status": "stable",
        "method": "coverage_only_v1",
        "rationale": [
            "no_regression_detected_over_threshold",
        ],
    }


def assemble_molecule_fact_sheet(
    db: Session,
    *,
    molecule_id: int,
    as_of: datetime,
    template_ids_used: list[str],
    policy_pins: dict[str, Any] | None = None,
    snapshot_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    as_of_iso = as_of.isoformat()
    out_snap = snapshot_output if isinstance(snapshot_output, dict) else {}
    template_ids = sorted(_ordered_unique([_norm_str(x) for x in template_ids_used]))
    required_metric_keys = _resolve_required_metric_keys(template_ids_used=template_ids, snapshot_output=out_snap)

    batch_rows = db.execute(
        text(
            """
            SELECT b.id, b.batch_id, b.title, b.created_at
            FROM batches b
            WHERE b.molecule_id = :molecule_id
            ORDER BY datetime(b.created_at) DESC, b.id DESC
            """
        ),
        {"molecule_id": int(molecule_id)},
    ).mappings().all()
    batch_meta = {
        int(r["id"]): {
            "batch_id": int(r["id"]),
            "batch_label": _norm_str(r["batch_id"]) or f"batch_id={int(r['id'])}",
            "batch_title": _norm_str(r["title"]),
            "batch_created_at": _norm_str(r["created_at"]),
        }
        for r in batch_rows
    }

    rec_rows = db.execute(
        text(
            """
            SELECT dr.id, dr.batch_id, dr.run_date, dr.created_at, dr.notes
            FROM data_records dr
            WHERE dr.molecule_id = :molecule_id
              AND datetime(dr.created_at) <= datetime(:as_of)
            ORDER BY datetime(dr.created_at) DESC, dr.id DESC
            """
        ),
        {"molecule_id": int(molecule_id), "as_of": as_of_iso},
    ).mappings().all()
    records = [
        {
            "id": int(r["id"]),
            "batch_id": (int(r["batch_id"]) if r["batch_id"] is not None else None),
            "run_date": _norm_str(r["run_date"]),
            "created_at": _norm_str(r["created_at"]),
            "notes": _norm_str(r["notes"]),
        }
        for r in rec_rows
    ]
    record_ids = [r["id"] for r in records]
    record_by_id = {r["id"]: r for r in records}

    cols = measurement_cols(db)
    rec_fk = cols["record_fk"]
    name_col = cols["name"]
    value_num_col = cols["value_num"] or "value_num"
    value_text_col = cols["value_text"] or "value_text"
    unit_col = cols["unit"] or "unit"
    qc_col = cols["qc_flag"] or "qc_flag"
    ignore_col = cols["ignore_for_model"] or "ignore_for_model"

    measurements: list[dict[str, Any]] = []
    if rec_fk and name_col and record_ids:
        params = {f"r{i}": rid for i, rid in enumerate(record_ids)}
        placeholders = ", ".join(f":r{i}" for i in range(len(record_ids)))
        sql = text(
            f"""
            SELECT
              id,
              {rec_fk} AS record_id,
              {name_col} AS metric_key,
              {value_num_col} AS value_num,
              {value_text_col} AS value_text,
              {unit_col} AS unit,
              {qc_col} AS qc_status,
              {ignore_col} AS ignore_for_model
            FROM data_measurements
            WHERE {rec_fk} IN ({placeholders})
            ORDER BY id DESC
            """
        )
        rows = db.execute(sql, params).mappings().all()
        for r in rows:
            rid = int(r["record_id"])
            measurements.append(
                {
                    "id": int(r["id"]),
                    "record_id": rid,
                    "batch_id": record_by_id.get(rid, {}).get("batch_id"),
                    "metric_key": normalize_metric_key(_norm_str(r["metric_key"])),
                    "raw_metric_key": _norm_str(r["metric_key"]),
                    "value_num": r["value_num"],
                    "value_text": r["value_text"],
                    "unit": r["unit"],
                    "qc_status": r["qc_status"],
                    "ignore_for_model": r["ignore_for_model"],
                }
            )

    # Deterministic batch columns: known batches first (desc date/id), then unassigned if needed.
    batch_columns: list[dict[str, Any]] = []
    for br in batch_rows:
        bid = int(br["id"])
        meta = batch_meta[bid]
        batch_columns.append(
            {
                "batch_id": bid,
                "batch_label": meta["batch_label"],
                "batch_date": meta["batch_created_at"],
            }
        )
    has_unassigned = any(m.get("batch_id") is None for m in measurements)
    if has_unassigned:
        batch_columns.append({"batch_id": None, "batch_label": "unassigned", "batch_date": ""})

    # Group measurements by (batch_id, metric_key) ordered by id DESC (already sorted query).
    grouped: dict[tuple[int | None, str], list[dict[str, Any]]] = defaultdict(list)
    observed_metric_keys: set[str] = set()
    for m in measurements:
        mk = normalize_metric_key(_norm_str(m.get("metric_key")))
        if not mk:
            continue
        observed_metric_keys.add(mk)
        grouped[(m.get("batch_id"), mk)].append(m)

    required_set = set(required_metric_keys)
    has_snapshot_gate_requirements = False
    gates_obj = out_snap.get("gates")
    if isinstance(gates_obj, list):
        for gate in gates_obj:
            if not isinstance(gate, dict):
                continue
            req_vals = gate.get("required_metrics") if isinstance(gate.get("required_metrics"), list) else []
            req_base_vals = gate.get("required_metrics_base") if isinstance(gate.get("required_metrics_base"), list) else []
            if req_vals or req_base_vals:
                has_snapshot_gate_requirements = True
                break
    ordered_metrics = _ordered_metric_keys(
        observed_metric_keys=observed_metric_keys,
        required_metric_keys=required_metric_keys,
        preserve_required_priority=has_snapshot_gate_requirements,
    )

    metric_descriptors = []
    matrix_rows = []
    required_present_by_batch = []
    for bc in batch_columns:
        bid = bc["batch_id"]
        req_present = 0
        total_present = 0
        for mk in ordered_metrics:
            cell_rows = grouped.get((bid, mk), [])
            if cell_rows:
                total_present += 1
            if mk in required_set and cell_rows:
                req_present += 1
        required_present_by_batch.append(
            {
                "batch_id": bid,
                "batch_label": bc["batch_label"],
                "required_present_count": int(req_present),
                "required_missing_count": int(max(0, len(required_metric_keys) - req_present)),
                "total_present_count": int(total_present),
            }
        )

    for mk in ordered_metrics:
        entry = metric_catalog_entry(mk)
        descriptor = {
            "metric_key": mk,
            "label": str(entry.get("label") or mk),
            "group": metric_group_for_key(mk),
            "unit": str(entry.get("unit") or ""),
            "required": bool(mk in required_set),
        }
        metric_descriptors.append(descriptor)
        cells = []
        for bc in batch_columns:
            bid = bc["batch_id"]
            candidates = grouped.get((bid, mk), [])
            selected = candidates[0] if candidates else None
            if selected is None:
                status = "missing"
                display = "not run"
                measurement_id = None
                record_id = None
                unit = ""
                value_num = None
                value_text = None
            else:
                qc_failed = _is_qc_failed(
                    qc_value=selected.get("qc_status"),
                    ignore_for_model=selected.get("ignore_for_model"),
                )
                if qc_failed:
                    status = "qc_failed"
                elif len(candidates) > 1:
                    status = "multiple"
                else:
                    status = "present"
                display = _display_value(
                    value_num=selected.get("value_num"),
                    value_text=selected.get("value_text"),
                    unit=selected.get("unit"),
                    metric_key=mk,
                )
                measurement_id = int(selected["id"])
                record_id = int(selected["record_id"])
                unit = _norm_str(selected.get("unit"))
                value_num = selected.get("value_num")
                value_text = selected.get("value_text")
            cells.append(
                {
                    "status": status,
                    "display": display,
                    "measurement_id": measurement_id,
                    "data_record_id": record_id,
                    "unit": unit,
                    "value_num": value_num,
                    "value_text": value_text,
                }
            )
        matrix_rows.append({"metric_key": mk, "cells": cells})

    # Batch registry with deterministic latest notes per batch.
    recs_by_batch: dict[int | None, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        recs_by_batch[rec["batch_id"]].append(rec)
    for bid in recs_by_batch:
        recs_by_batch[bid] = sorted(
            recs_by_batch[bid],
            key=lambda r: (_norm_str(r.get("created_at")), int(r.get("id") or 0)),
            reverse=True,
        )

    batch_registry = []
    for bc in batch_columns:
        bid = bc["batch_id"]
        recs = recs_by_batch.get(bid, [])
        latest = recs[0] if recs else {}
        metric_keys = sorted(
            {
                normalize_metric_key(_norm_str(m.get("metric_key")))
                for m in measurements
                if m.get("batch_id") == bid and normalize_metric_key(_norm_str(m.get("metric_key")))
            }
        )
        coverage_groups = sorted({metric_group_for_key(mk) for mk in metric_keys}, key=metric_group_sort_key)
        batch_registry.append(
            {
                "batch_id": bid,
                "batch_label": bc["batch_label"],
                "batch_date": (_norm_str(latest.get("run_date")) or bc["batch_date"] or "unknown"),
                "producer": "unknown",
                "purpose_notes": (_norm_str(batch_meta.get(bid, {}).get("batch_title")) or "unknown"),
                "data_coverage_summary": (", ".join(coverage_groups) if coverage_groups else "none"),
                "metric_keys": metric_keys,
                "latest_notes": _norm_str(latest.get("notes")),
                "record_count": len(recs),
            }
        )

    coverage_summary = {
        "batch_count": len(batch_columns),
        "record_count": len(records),
        "measurement_count": len(measurements),
        "required_metric_count": len(required_metric_keys),
        "required_present_by_batch": required_present_by_batch,
    }
    best_batch = _compute_best_batch(
        required_present_by_batch=required_present_by_batch,
        batch_registry=batch_registry,
    )

    stability = _compute_stability(
        required_present_by_batch=required_present_by_batch,
        best_batch=best_batch,
        batch_registry=batch_registry,
    )

    return {
        "schema_version": "v1",
        "meta": {"as_of": as_of_iso},
        "metrics_index": {
            "template_ids_used": template_ids,
            "required_metric_keys": required_metric_keys,
            "metrics": metric_descriptors,
        },
        "batch_registry": batch_registry,
        "metric_matrix": {
            "batch_columns": batch_columns,
            "rows": matrix_rows,
        },
        "coverage_summary": coverage_summary,
        "best_batch": best_batch,
        "stability": stability,
    }
