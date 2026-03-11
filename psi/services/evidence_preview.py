from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.models import DataRecord, DecisionSnapshot
from psi.services.di.util import is_di_snapshot_record
from psi.services.metric_catalog import metric_catalog_entry


def _record_metric_keys(db: Session, *, record_id: int) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT dm.metric_key AS metric_key
            FROM data_measurements dm
            WHERE dm.data_record_id = :rid
            ORDER BY dm.metric_key ASC, dm.id ASC
            """
        ),
        {"rid": int(record_id)},
    ).mappings().all()
    out: list[str] = []
    seen: set[str] = set()
    for r in rows:
        mk = str(r.get("metric_key") or "").strip()
        if not mk or mk in seen:
            continue
        seen.add(mk)
        out.append(mk)
    return out


def _latest_snapshot_metric_keys_for_molecule(
    db: Session,
    *,
    molecule_id: int,
    cache: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    mid = int(molecule_id)
    if isinstance(cache, dict) and mid in cache:
        return cache[mid]

    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == mid)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    out_obj = {"snapshot_id": None, "metric_keys": []}
    for snap in snaps:
        try:
            out = json.loads(snap.outputs_json or "{}")
        except Exception:
            out = {}
        try:
            inn = json.loads(snap.inputs_json or "{}")
        except Exception:
            inn = {}
        if not isinstance(out, dict):
            out = {}
        if not isinstance(inn, dict):
            inn = {}
        if not is_di_snapshot_record(snap, out, inn):
            continue
        used_by_metric = out.get("used_by_metric") if isinstance(out.get("used_by_metric"), dict) else {}
        out_obj = {
            "snapshot_id": int(snap.id),
            "metric_keys": sorted(str(k).strip() for k in used_by_metric.keys() if str(k).strip()),
        }
        break

    if isinstance(cache, dict):
        cache[mid] = out_obj
    return out_obj


def build_record_evidence_preview(
    db: Session,
    *,
    record_id: int,
    latest_snapshot_cache: dict[int, dict[str, Any]] | None = None,
    record_metric_keys: list[str] | None = None,
    molecule_id: int | None = None,
) -> dict[str, Any]:
    rec = None
    if record_metric_keys is None or molecule_id is None:
        rec = db.get(DataRecord, int(record_id))
        if rec is None:
            raise KeyError("DataRecord not found")

    if record_metric_keys is None:
        record_keys = _record_metric_keys(db, record_id=int(record_id))
    else:
        seen: set[str] = set()
        record_keys = []
        for mk in list(record_metric_keys or []):
            key = str(mk or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            record_keys.append(key)

    record_molecule_id = (
        int(molecule_id)
        if molecule_id is not None
        else (int(rec.molecule_id) if rec is not None and rec.molecule_id is not None else None)
    )
    latest = (
        _latest_snapshot_metric_keys_for_molecule(
            db,
            molecule_id=int(record_molecule_id),
            cache=latest_snapshot_cache,
        )
        if record_molecule_id is not None
        else {"snapshot_id": None, "metric_keys": []}
    )
    latest_keys = [str(x) for x in (latest.get("metric_keys") or []) if str(x).strip()]
    latest_key_set = set(latest_keys)

    rows: list[dict[str, Any]] = []
    for mk in record_keys:
        meta = metric_catalog_entry(mk)
        present = mk in latest_key_set
        rows.append(
            {
                "metric_key": mk,
                "label": str(meta.get("label") or mk),
                "domain": str(meta.get("domain") or "Other"),
                "status_key": ("already_present" if present else "new_vs_last_snapshot"),
                "status_label": ("Already present" if present else "New vs last snapshot"),
            }
        )
    rows = sorted(
        rows,
        key=lambda r: (
            str(r.get("domain") or ""),
            str(r.get("label") or ""),
            str(r.get("metric_key") or ""),
        ),
    )

    new_count = len([r for r in rows if str(r.get("status_key") or "") == "new_vs_last_snapshot"])
    existing_count = len([r for r in rows if str(r.get("status_key") or "") == "already_present"])
    return {
        "record_id": int(record_id),
        "molecule_id": record_molecule_id,
        "latest_snapshot_id": latest.get("snapshot_id"),
        "latest_snapshot_metric_keys": latest_keys,
        "rows": rows,
        "counts": {
            "total_metrics": len(rows),
            "new_vs_last_snapshot": int(new_count),
            "already_present": int(existing_count),
        },
    }


def build_pending_evidence_preview_for_molecule(
    db: Session,
    *,
    molecule_id: int,
) -> list[dict[str, Any]]:
    rows = db.execute(
        text(
            """
            SELECT
              dr.id AS record_id,
              dr.created_at AS created_at,
              dr.title AS title,
              dr.data_type AS data_type,
              dr.method AS method,
              COUNT(dm.id) AS total_measurements,
              SUM(CASE WHEN COALESCE(qc.status, 'unreviewed') = 'approved' THEN 1 ELSE 0 END) AS approved_measurements
            FROM data_records dr
            LEFT JOIN data_measurements dm ON dm.data_record_id = dr.id
            LEFT JOIN measurement_qc qc ON qc.measurement_id = dm.id
            WHERE dr.molecule_id = :mid
            GROUP BY dr.id, dr.created_at, dr.title, dr.data_type, dr.method
            ORDER BY dr.created_at DESC, dr.id DESC
            """
        ),
        {"mid": int(molecule_id)},
    ).mappings().all()

    pending_record_ids = [
        int(r.get("record_id"))
        for r in rows
        if int(r.get("total_measurements") or 0) == 0
        or int(r.get("approved_measurements") or 0) < int(r.get("total_measurements") or 0)
    ]
    cache: dict[int, dict[str, Any]] = {}
    preview_by_id = {
        rid: build_record_evidence_preview(db, record_id=int(rid), latest_snapshot_cache=cache)
        for rid in pending_record_ids
    }

    out: list[dict[str, Any]] = []
    for r in rows:
        rid = int(r.get("record_id"))
        if rid not in preview_by_id:
            continue
        prev = preview_by_id[rid]
        out.append(
            {
                "record_id": rid,
                "created_at": str(r.get("created_at") or ""),
                "title": str(r.get("title") or ""),
                "assay_key": f"{str(r.get('data_type') or '')}/{str(r.get('method') or '')}",
                "counts": dict(prev.get("counts") or {}),
                "rows": list(prev.get("rows") or []),
            }
        )
    return out
