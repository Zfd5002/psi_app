from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_all_cols, measurement_cols
from psi.core.models import MeasurementQC
from psi.core.di.schema import EvidenceRef, IgnoredEvidence


# v1.2.9d: stable ignored-evidence taxonomy (no ad-hoc strings)
ALLOWED_IGNORE_REASON_KEYS = {
    "qc_failed",
    "qc_unreviewed_strict",
    "superseded_by_primary",
    "superseded_by_newer",
    "outlier_policy",
    "metric_not_applicable",
    "unit_inconvertible",
    "method_incomparable",
    "as_of_excluded",
}


def _parse_iso(ts: Optional[str]) -> Optional[_dt.datetime]:
    if not ts:
        return None
    s = str(ts).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return dt


def _qc_status_from_flag(raw: Any) -> str:
    # Back-compat: older tooling uses qc_flag like a boolean "flagged".
    if raw in (None, "", 0, "0"):
        return "unreviewed"
    s = str(raw).strip().lower()
    if s in ("approved", "pass", "ok"):
        return "approved"
    if s in ("rejected", "fail", "bad", "flagged", "1", "true"):
        return "rejected"
    if s in ("quarantined", "quarantine"):
        return "quarantined"
    return "unknown"


def _accept_qc(qc_mode: str, qc_status: str, policy_qc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    m = (qc_mode or "model_safe").strip()
    conf = (policy_qc or {}).get(m) or {}
    accept = set(str(x) for x in (conf.get("accept_statuses") or []))
    reject = set(str(x) for x in (conf.get("reject_statuses") or []))
    treat_unreviewed_as = str(conf.get("treat_unreviewed_as") or "accept")

    if qc_status in reject:
        return False, "qc_failed"
    if qc_status == "unreviewed" and m == "strict":
        return False, "qc_unreviewed_strict"
    if qc_status in accept:
        if qc_status == "unreviewed" and treat_unreviewed_as == "accept_with_flag":
            return True, "qc_unreviewed_accepted"
        return True, None

    # unknown status: strict rejects; others accept but flag
    if m == "strict":
        return False, "qc_unreviewed_strict"
    return True, "qc_unknown_accepted"


def select_batch_measurements(
    db: Session,
    *,
    batch_id: int,
    as_of_ts: Optional[str],
    qc_mode: str,
    metric_alias_map: Dict[str, List[str]],
    policy_qc: Dict[str, Any],
) -> Dict[str, Any]:
    cols = measurement_cols(db)
    _ = measurement_all_cols(db)  # ensure reflection cache warm

    record_fk = cols["record_fk"]
    name_col = cols["name"]
    id_col = cols["id"] or "id"
    produced_col = cols.get("produced_at")
    created_col = cols.get("created_at")
    updated_col = cols.get("updated_at")
    is_primary_col = cols.get("is_primary")
    is_outlier_col = cols.get("is_outlier")
    ignore_col = cols.get("ignore_for_model")
    qc_flag_col = cols.get("qc_flag")

    q = text(
        f"""
        SELECT
          dm.*,
          dr.id as _dr_id
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dr.batch_id = :bid
        ORDER BY dm.{id_col} ASC
        """
    )
    rows = db.execute(q, {"bid": int(batch_id)}).mappings().all()

    mids = []
    for r in rows:
        v = r.get(id_col) if id_col in r else r.get("id")
        if v is None:
            continue
        try:
            mids.append(int(v))
        except Exception:
            continue

    qc_map: Dict[int, str] = {}
    if mids:
        for mq in db.query(MeasurementQC).filter(MeasurementQC.measurement_id.in_(mids)).all():
            if mq.measurement_id is not None and mq.status:
                qc_map[int(mq.measurement_id)] = str(mq.status)

    dt_asof = _parse_iso(as_of_ts) if as_of_ts else None

    alias_to_canonical: Dict[str, str] = {}
    for canon, aliases in (metric_alias_map or {}).items():
        for a in aliases or []:
            alias_to_canonical[str(a)] = str(canon)

    used_by_metric: Dict[str, EvidenceRef] = {}
    ignored: List[IgnoredEvidence] = []
    warnings: List[Dict[str, Any]] = []

    qc_source_counts_used: Dict[str, int] = {"measurement_qc": 0, "qc_flag_fallback": 0, "unknown": 0}

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        mk_raw = r.get(name_col)
        mk = str(mk_raw).strip() if mk_raw is not None else ""
        if not mk:
            continue
        canon = alias_to_canonical.get(mk, mk)
        grouped.setdefault(canon, []).append(r)

    def row_dt(r: Dict[str, Any]) -> Tuple[Optional[_dt.datetime], Optional[_dt.datetime]]:
        dp = _parse_iso(str(r.get(produced_col))) if produced_col and r.get(produced_col) is not None else None
        dc = _parse_iso(str(r.get(created_col) or r.get(updated_col))) if (created_col or updated_col) and (r.get(created_col) is not None or r.get(updated_col) is not None) else None
        return dp, dc

    def row_id(r: Dict[str, Any]) -> int:
        v = r.get(id_col) if id_col in r else r.get("id")
        try:
            return int(v)
        except Exception:
            return 0

    for canon, rs in grouped.items():
        candidates: List[Tuple[Dict[str, Any], EvidenceRef, Optional[str]]] = []

        for r in rs:
            mid = row_id(r)
            drid = int(r.get("_dr_id"))
            mk_raw = str(r.get(name_col)).strip()
            metric_key_source = "canonical" if mk_raw == canon else f"alias:{mk_raw}"

            if ignore_col and int(r.get(ignore_col) or 0) == 1:
                ignored.append(IgnoredEvidence(mid, drid, canon, "outlier_policy", reason_detail="ignore_for_model", qc_source=None))
                continue

            dp, dc = row_dt(r)
            if dt_asof is not None:
                chk = dp or dc
                if chk is not None and chk > dt_asof:
                    ignored.append(IgnoredEvidence(mid, drid, canon, "as_of_excluded", reason_detail=str(as_of_ts or ""), qc_source=None))
                    continue

            qc_status = qc_map.get(mid) or _qc_status_from_flag(r.get(qc_flag_col) if qc_flag_col else None)
            if mid in qc_map:
                qc_source = "measurement_qc"
            elif qc_flag_col:
                qc_source = "qc_flag_fallback"
            else:
                qc_source = "unknown"
            ok, qc_reason = _accept_qc(qc_mode, qc_status, policy_qc)
            if not ok:
                rk = str(qc_reason or "qc_failed")
                if rk not in ALLOWED_IGNORE_REASON_KEYS:
                    rk = "qc_failed"
                ignored.append(IgnoredEvidence(mid, drid, canon, rk, reason_detail=None, qc_source=qc_source))
                continue

            val_num = r.get(cols.get("value_num"))
            val_text = r.get(cols.get("value_text"))
            val_bool_raw = r.get(cols.get("value_bool")) if cols.get("value_bool") else r.get("value_bool")

            vb: Optional[bool]
            if isinstance(val_bool_raw, bool):
                vb = val_bool_raw
            elif isinstance(val_bool_raw, int):
                vb = bool(val_bool_raw)
            elif isinstance(val_bool_raw, str) and val_bool_raw.strip().lower() in ("true", "false"):
                vb = (val_bool_raw.strip().lower() == "true")
            else:
                vb = None

            ev = EvidenceRef(
                measurement_id=mid,
                data_record_id=drid,
                metric_key=canon,
                metric_key_source=metric_key_source,
                value_num=(float(val_num) if val_num is not None and not isinstance(val_num, bool) else None),
                value_text=(str(val_text).strip() if isinstance(val_text, str) and val_text.strip() else None),
                value_bool=vb,
                unit=(str(r.get(cols.get("unit"))).strip() if cols.get("unit") and r.get(cols.get("unit")) is not None else None),
                comparator=(str(r.get(cols.get("comparator"))).strip() if cols.get("comparator") and r.get(cols.get("comparator")) is not None else None),
                qc_status=qc_status,
                qc_flag_raw=(str(r.get(qc_flag_col)) if qc_flag_col and r.get(qc_flag_col) is not None else None),
                qc_source=qc_source,
                is_primary=(bool(int(r.get(is_primary_col) or 0)) if is_primary_col else False),
                is_outlier=(bool(int(r.get(is_outlier_col) or 0)) if is_outlier_col else False),
                produced_at=(str(r.get(produced_col)) if produced_col and r.get(produced_col) is not None else None),
                created_at=(str(r.get(created_col)) if created_col and r.get(created_col) is not None else None),
            )

            if qc_reason in ("qc_unreviewed_accepted", "qc_unknown_accepted"):
                warnings.append({"kind": "qc_uncertainty", "measurement_id": mid, "metric_key": canon, "detail": qc_reason})

            candidates.append((r, ev, qc_reason))

        if not candidates:
            continue

        def norm(dt: Optional[_dt.datetime]) -> _dt.datetime:
            return dt if dt is not None else _dt.datetime(1970, 1, 1)

        def sort_key(tup):
            r, ev, _ = tup
            dp, dc = row_dt(r)
            return (
                1 if ev.is_primary else 0,
                norm(dp),
                norm(dc),
                row_id(r),
            )

        candidates.sort(key=sort_key, reverse=True)
        chosen_r, chosen_ev, _ = candidates[0]
        used_by_metric[canon] = chosen_ev
        qc_source_counts_used[chosen_ev.qc_source] = qc_source_counts_used.get(chosen_ev.qc_source, 0) + 1

        for (r, ev, _) in candidates[1:]:
            rk = "superseded_by_primary" if (chosen_ev.is_primary and not ev.is_primary) else "superseded_by_newer"
            reason_detail = f"chosen_measurement_id={chosen_ev.measurement_id}"
            ignored.append(IgnoredEvidence(ev.measurement_id, ev.data_record_id, canon, rk, reason_detail=reason_detail, qc_source=ev.qc_source))

    # flag: outlier present anywhere in used evidence
    if any(ev.is_outlier for ev in used_by_metric.values()):
        warnings.append({"kind": "outlier_present", "detail": {"measurement_ids": sorted([ev.measurement_id for ev in used_by_metric.values() if ev.is_outlier])}})

    # alias conflict: if canonical + alias both existed for a concept
    for canon, rs in grouped.items():
        raw_keys = sorted({str(r.get(name_col)).strip() for r in rs if r.get(name_col) is not None})
        if canon in raw_keys and any(k != canon for k in raw_keys):
            warnings.append({"kind": "conflicting_metrics", "metric_key": canon, "detail": {"raw_keys": raw_keys}})

    # Deterministic ordering for ignored evidence
    ignored.sort(key=lambda x: (str(x.metric_key), int(x.measurement_id)))

    return {
        "used_by_metric": used_by_metric,
        "ignored": ignored,
        "warnings": warnings,
        "alias_to_canonical": alias_to_canonical,
        "selection_provenance": {
            "qc_source_counts_used": qc_source_counts_used,
            "tie_break": "is_primary_first_else_newest_timestamp_else_measurement_id",
        },
    }
