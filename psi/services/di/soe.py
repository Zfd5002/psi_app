from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_cols
from psi.services.di.util import parse_iso, qc_status_from_flag


import datetime as _dt


@dataclass(frozen=True)
class SoECoreConfig:
    schema_version: str
    scope_kind: str
    db: Session
    batch_id: Optional[int] = None
    molecule_id: Optional[int] = None
    batch_ids: Optional[List[int]] = None
    decision_key: str = ""
    policy_body: Optional[Dict[str, Any]] = None
    used_by_metric: Optional[Dict[str, Any]] = None
    ignored: Optional[list[Any]] = None
    warnings: Optional[list[Dict[str, Any]]] = None
    qc_mode: str = ""
    context: Optional[Dict[str, Any]] = None
    as_of_ts: Optional[str] = None

    # Compatibility shim to keep _build_soe_core internals unchanged while typing
    # the config object at the public entrypoints.
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _timestamp_used(produced_at: Optional[str], created_at: Optional[str]) -> Dict[str, Any]:
    dp = parse_iso(produced_at)
    dc = parse_iso(created_at)
    if dp is not None:
        return {"timestamp_used": "produced_at", "timestamp_value": produced_at}
    if dc is not None:
        return {"timestamp_used": "created_at", "timestamp_value": created_at}
    return {"timestamp_used": None, "timestamp_value": None}


def _fetch_batch_metric_keys_raw(db: Session, *, batch_id: int) -> list[str]:
    cols = measurement_cols(db)
    record_fk = cols["record_fk"]
    name_col = cols["name"]

    q = text(
        f"""
        SELECT DISTINCT dm.{name_col} AS metric_key
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dr.batch_id = :bid
        """
    )
    rows = db.execute(q, {"bid": int(batch_id)}).mappings().all()
    out: list[str] = []
    for r in rows:
        mk = r.get("metric_key")
        if mk is None:
            continue
        s = str(mk).strip()
        if s:
            out.append(s)
    return sorted(set(out))


def _dedupe_preserve_order_ints(batch_ids: List[int]) -> List[int]:
    out: List[int] = []
    seen: set[int] = set()
    for x in batch_ids or []:
        try:
            xi = int(x)
        except Exception:
            continue
        if xi <= 0:
            continue
        if xi in seen:
            continue
        seen.add(xi)
        out.append(xi)
    return out


def _fetch_metric_keys_raw_for_batches(db: Session, *, batch_ids: List[int]) -> list[str]:
    batch_ids = _dedupe_preserve_order_ints(batch_ids)
    if not batch_ids:
        return []
    cols = measurement_cols(db)
    record_fk = cols["record_fk"]
    name_col = cols["name"]

    q = text(
        f"""
        SELECT DISTINCT dm.{name_col} AS metric_key
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dr.batch_id IN :bids
        """
    ).bindparams(bindparam("bids", expanding=True))
    rows = db.execute(q, {"bids": list(batch_ids)}).mappings().all()
    out: list[str] = []
    for r in rows:
        mk = r.get("metric_key")
        if mk is None:
            continue
        s = str(mk).strip()
        if s:
            out.append(s)
    return sorted(set(out))


def _related_keys_detect_only(missing_key: str, raw_keys: list[str]) -> list[str]:
    mk = str(missing_key)
    suffixes = ("_pct", "_percent", "_percentage")
    base = mk
    for suf in suffixes:
        if mk.endswith(suf):
            base = mk[: -len(suf)]
            break

    rel: list[str] = []
    if not base:
        return rel

    for rk in raw_keys:
        if rk == mk:
            continue
        if not rk.startswith(base):
            continue
        if rk.endswith(suffixes):
            rel.append(rk)

    return sorted(set(rel))


def _policy_gate_requirements(policy_body: Dict[str, Any]) -> tuple[Dict[str, Any], list[str], Dict[str, Any], list[str]]:
    gates = (policy_body or {}).get("gates") or {}
    if not isinstance(gates, dict):
        gates = {}

    gate_keys = sorted([str(k) for k in gates.keys()])
    requirements_by_gate: Dict[str, Any] = {}
    referenced_metrics: set[str] = set()

    for gk in gate_keys:
        gd = gates.get(gk) or {}
        if not isinstance(gd, dict):
            gd = {}
        req_type = "require_all" if "require_all" in gd else ("require_any" if "require_any" in gd else "")
        req_list = gd.get("require_all") if "require_all" in gd else gd.get("require_any")
        req_list = req_list if isinstance(req_list, list) else []
        required = sorted([str(x) for x in req_list if str(x).strip()])
        referenced_metrics.update(required)

        entry: Dict[str, Any] = {"requirement_type": req_type, "required": required, "notes": []}
        for ck in ("enabled", "if_present", "context_knob"):
            if ck in gd:
                entry[ck] = gd.get(ck)
        requirements_by_gate[gk] = entry

    return gates, gate_keys, requirements_by_gate, sorted(referenced_metrics)


def _ignored_by_metric_map(ignored: list[Any]) -> Dict[str, list[Any]]:
    ignored_by_metric: Dict[str, list[Any]] = {}
    for ig in ignored or []:
        try:
            mk = str(getattr(ig, "metric_key", "") or "").strip()
        except Exception:
            mk = ""
        if mk:
            ignored_by_metric.setdefault(mk, []).append(ig)
    return ignored_by_metric


def _build_metric_status_v0_2(
    *,
    metrics_sorted: list[str],
    used_by_metric: Dict[str, Any],
    ignored_by_metric: Dict[str, list[Any]],
    raw_keys: list[str],
    warnings: list[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, int]]:
    metric_status: Dict[str, Any] = {}
    NON_NUMERIC_OK = {"pass_fail"}
    present_via_alias = 0
    alias_conflicts = 0
    unmapped_related_detected = 0

    for mk in metrics_sorted:
        ev = used_by_metric.get(mk)
        igs = ignored_by_metric.get(mk) or []

        status = "missing"
        selected_id = None
        qc_status = None
        produced_at = None
        created_at = None
        metric_key_source = None
        notes: list[str] = []
        related: list[str] = []

        if ev is not None:
            status = "present"
            selected_id = getattr(ev, "measurement_id", None)
            qc_status = getattr(ev, "qc_status", None)
            produced_at = getattr(ev, "produced_at", None)
            created_at = getattr(ev, "created_at", None)
            metric_key_source = getattr(ev, "metric_key_source", None)

            if mk not in NON_NUMERIC_OK:
                vn = getattr(ev, "value_num", None)
                if vn is None:
                    status = "present_but_non_numeric"

            if isinstance(metric_key_source, str) and metric_key_source.startswith("alias:"):
                present_via_alias += 1
                notes.append(f"present via alias mapping from {metric_key_source.split(':',1)[1]}")
        elif igs:
            status = "present_but_ignored"
            try:
                selected_id = int(
                    sorted(
                        [
                            int(getattr(x, "measurement_id", 0) or 0)
                            for x in igs
                            if getattr(x, "measurement_id", None) is not None
                        ]
                    )[0]
                )
            except Exception:
                selected_id = None

        if status == "missing":
            related = _related_keys_detect_only(mk, raw_keys)
            if related:
                unmapped_related_detected += 1
                notes.append("missing canonical key; related metric keys present (detect-only)")

        for w in warnings or []:
            if isinstance(w, dict) and w.get("kind") == "conflicting_metrics" and str(w.get("metric_key")) == mk:
                alias_conflicts += 1
                notes.append("conflicting raw metric keys present for this concept")
                break

        ts = _timestamp_used(produced_at, created_at)
        metric_status[mk] = {
            "status": status,
            "selected_measurement_id": selected_id,
            "qc_status": qc_status,
            "timestamp_used": ts["timestamp_used"],
            "produced_at": produced_at,
            "created_at": created_at,
            "metric_key_source": metric_key_source,
            "related_metric_keys_present": related,
            "notes": notes,
        }

    counters = {
        "present_via_alias": int(present_via_alias),
        "alias_conflicts": int(alias_conflicts),
        "unmapped_related_detected": int(unmapped_related_detected),
    }
    return metric_status, counters


def _build_gate_coverage_v0_2(
    *,
    gates: Dict[str, Any],
    gate_keys: list[str],
    metric_status: Dict[str, Any],
    include_satisfied: bool,
    sort_present_missing: bool,
) -> Dict[str, Any]:
    gate_coverage: Dict[str, Any] = {}
    for gk in gate_keys:
        gd = gates.get(gk) or {}
        if not isinstance(gd, dict):
            gd = {}
        req_type = "require_all" if "require_all" in gd else ("require_any" if "require_any" in gd else "")
        req_list = gd.get("require_all") if "require_all" in gd else gd.get("require_any")
        req_list = req_list if isinstance(req_list, list) else []
        required = sorted([str(x) for x in req_list if str(x).strip()])

        present: list[str] = []
        missing: list[str] = []
        for m in required:
            st = (metric_status.get(m) or {}).get("status")
            if st in ("present", "present_but_non_numeric"):
                present.append(m)
            else:
                missing.append(m)

        item: Dict[str, Any] = {
            "requirement_type": req_type,
            "required": required,
            "present": sorted(present) if sort_present_missing else present,
            "missing": sorted(missing) if sort_present_missing else missing,
        }
        if include_satisfied:
            satisfied = False
            if req_type == "require_all":
                satisfied = len(missing) == 0
            elif req_type == "require_any":
                satisfied = len(present) > 0
            item["satisfied"] = bool(satisfied)
        gate_coverage[gk] = item
    return gate_coverage


def _soe_v0_2_recency_from_metric_status(metrics_sorted: list[str], metric_status: Dict[str, Any]) -> Dict[str, Any]:
    per_metric_rec: Dict[str, Any] = {}
    ts_values: list[_dt.datetime] = []
    basis_set: set[str] = set()

    for mk in metrics_sorted:
        ms = metric_status.get(mk) or {}
        tu = ms.get("timestamp_used")
        pv = ms.get("produced_at")
        cv = ms.get("created_at")
        tv = pv if tu == "produced_at" else (cv if tu == "created_at" else None)

        per_metric_rec[mk] = {"timestamp_used": tu, "timestamp_value": tv, "produced_at": pv, "created_at": cv}

        if tu in ("produced_at", "created_at"):
            basis_set.add(str(tu))
        dtv = parse_iso(tv) if isinstance(tv, str) else None
        if dtv is not None:
            ts_values.append(dtv)

    if not ts_values:
        batch_rec = {"newest_timestamp": None, "oldest_timestamp": None, "timestamp_basis": None}
    else:
        newest = max(ts_values).isoformat()
        oldest = min(ts_values).isoformat()
        if len(basis_set) == 1:
            basis = list(basis_set)[0]
        elif len(basis_set) > 1:
            basis = "mixed"
        else:
            basis = None
        batch_rec = {"newest_timestamp": newest, "oldest_timestamp": oldest, "timestamp_basis": basis}
    return {"per_metric": per_metric_rec, "batch": batch_rec}


def _build_alias_to_canonical(policy_body: Dict[str, Any]) -> Dict[str, str]:
    alias_to_canonical: Dict[str, str] = {}
    for canon, aliases in ((policy_body or {}).get("metric_alias_map") or {}).items():
        for a in aliases or []:
            sa = str(a).strip()
            sc = str(canon).strip()
            if sa and sc:
                alias_to_canonical[sa] = sc
    return alias_to_canonical


def _referenced_metrics_from_policy(policy_body: Dict[str, Any]) -> list[str]:
    _, _, _, metrics_sorted = _policy_gate_requirements(policy_body)
    return metrics_sorted


def _build_qc_acceptor(policy_body: Dict[str, Any], qc_mode: str):
    policy_qc = (policy_body or {}).get("qc_modes") or {}
    qc_conf = (policy_qc.get(qc_mode) or {}) if isinstance(policy_qc, dict) else {}
    accept = set(str(x) for x in (qc_conf.get("accept_statuses") or []))
    reject = set(str(x) for x in (qc_conf.get("reject_statuses") or []))

    def accept_qc(qs: str) -> bool:
        if qs in reject:
            return False
        if qs == "unreviewed" and str(qc_mode) == "strict":
            return False
        if qs in accept:
            return True
        if str(qc_mode) == "strict":
            return False
        return True

    return accept_qc


def _fetch_v0_3_measurement_rows_for_batches(db: Session, *, batch_ids: List[int]) -> List[Dict[str, Any]]:
    batch_ids = _dedupe_preserve_order_ints(batch_ids)
    if not batch_ids:
        return []
    cols = measurement_cols(db)
    record_fk = cols["record_fk"]
    name_col = cols["name"]
    id_col = cols.get("id") or "id"
    unit_col = cols.get("unit")
    method_col = cols.get("method")
    produced_col = cols.get("produced_at")
    created_col = cols.get("created_at")
    updated_col = cols.get("updated_at")
    ignore_col = cols.get("ignore_for_model")
    qc_flag_col = cols.get("qc_flag")
    q = text(
        f"""
        SELECT
          dm.{id_col} as mid,
          dm.{name_col} as metric_key,
          {('dm.' + unit_col) if unit_col else 'NULL'} as unit,
          {('dm.' + method_col) if method_col else 'NULL'} as method,
          {('dm.' + produced_col) if produced_col else 'NULL'} as produced_at,
          {('dm.' + created_col) if created_col else (('dm.' + updated_col) if updated_col else 'NULL')} as created_at,
          {('dm.' + ignore_col) if ignore_col else '0'} as ignore_for_model,
          {('dm.' + qc_flag_col) if qc_flag_col else 'NULL'} as qc_flag,
          dr.id as drid
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dr.batch_id IN :bids
        ORDER BY dm.{id_col} ASC
        """
    ).bindparams(bindparam("bids", expanding=True))
    return db.execute(q, {"bids": list(batch_ids)}).mappings().all()


def _group_rows_for_soe_v0_3(
    *,
    rows: List[Dict[str, Any]],
    alias_to_canonical: Dict[str, str],
    dt_asof: Optional[_dt.datetime],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        mk_raw = r.get("metric_key")
        mk = str(mk_raw).strip() if mk_raw is not None else ""
        if not mk:
            continue
        canon = alias_to_canonical.get(mk, mk)

        if dt_asof is not None:
            dp = parse_iso(r.get("produced_at"))
            dc = parse_iso(r.get("created_at"))
            chk = dp or dc
            if chk is not None and chk > dt_asof:
                continue

        grouped.setdefault(canon, []).append(r)
    return grouped


def _build_evidence_summary_v0_3(
    *,
    referenced_metrics: list[str],
    grouped: Dict[str, List[Dict[str, Any]]],
    ignored_by_metric: Dict[str, List[Any]],
    accept_qc,
) -> List[Dict[str, Any]]:
    evidence_summary: List[Dict[str, Any]] = []
    for mk in referenced_metrics:
        rs = grouped.get(mk) or []
        total_count = len(rs)
        methods_present: List[str] = []
        units_present: List[str] = []
        latest_dt: Optional[_dt.datetime] = None
        usable_count = 0
        for r in rs:
            m = r.get("method")
            u = r.get("unit")
            if m is not None and str(m).strip():
                methods_present.append(str(m).strip())
            if u is not None and str(u).strip():
                units_present.append(str(u).strip())

            dp = parse_iso(r.get("produced_at"))
            dc = parse_iso(r.get("created_at"))
            chk = dp or dc
            if chk is not None and (latest_dt is None or chk > latest_dt):
                latest_dt = chk

            if int(r.get("ignore_for_model") or 0) == 1:
                continue
            qs = qc_status_from_flag(r.get("qc_flag"))
            if accept_qc(qs):
                usable_count += 1

        igs = ignored_by_metric.get(mk) or []
        breakdown: Dict[str, int] = {}
        for ig in igs:
            try:
                rk = str(getattr(ig, "reason_key", "") or "").strip()
            except Exception:
                rk = ""
            if not rk:
                continue
            breakdown[rk] = breakdown.get(rk, 0) + 1

        evidence_summary.append(
            {
                "metric_key": mk,
                "total_count": int(total_count),
                "usable_count": int(usable_count),
                "ignored_count": int(len(igs)),
                "latest_timestamp": latest_dt.isoformat() if latest_dt is not None else None,
                "methods_present": sorted(set(methods_present)),
                "units_present": sorted(set(units_present)),
                "ignore_reasons_breakdown": [
                    {"reason_key": rk, "count": int(breakdown[rk])} for rk in sorted(breakdown.keys())
                ],
            }
        )
    return evidence_summary


def _build_soe_core(*, config: SoECoreConfig) -> Dict[str, Any]:
    schema_version = str((config or {}).get("schema_version") or "")
    scope_kind = str((config or {}).get("scope_kind") or "batch")
    db = config.get("db")
    if not isinstance(db, Session):
        raise TypeError("config.db must be a SQLAlchemy Session")

    if schema_version == "0.2":
        policy_body = (config or {}).get("policy_body") or {}
        used_by_metric = (config or {}).get("used_by_metric") or {}
        ignored = (config or {}).get("ignored") or []
        warnings = (config or {}).get("warnings") or []
        qc_mode = str((config or {}).get("qc_mode") or "")
        decision_key = str((config or {}).get("decision_key") or "")

        gates, gate_keys, requirements_by_gate, metrics_sorted = _policy_gate_requirements(policy_body)
        if scope_kind == "molecule":
            batch_ids = _dedupe_preserve_order_ints((config or {}).get("batch_ids") or [])
            raw_keys = _fetch_metric_keys_raw_for_batches(db, batch_ids=batch_ids)
        else:
            batch_id = int((config or {}).get("batch_id") or 0)
            raw_keys = _fetch_batch_metric_keys_raw(db, batch_id=batch_id)

        ignored_by_metric = _ignored_by_metric_map(ignored)
        metric_status, status_counts_ext = _build_metric_status_v0_2(
            metrics_sorted=metrics_sorted,
            used_by_metric=used_by_metric,
            ignored_by_metric=ignored_by_metric,
            raw_keys=raw_keys,
            warnings=warnings,
        )
        gate_coverage = _build_gate_coverage_v0_2(
            gates=gates,
            gate_keys=gate_keys,
            metric_status=metric_status,
            include_satisfied=(scope_kind != "molecule"),
            sort_present_missing=(scope_kind != "molecule"),
        )

        if scope_kind == "molecule":
            batch_ids = _dedupe_preserve_order_ints((config or {}).get("batch_ids") or [])
            molecule_id = int((config or {}).get("molecule_id") or 0)
            total_required = sum(len((gate_coverage.get(gk) or {}).get("required") or []) for gk in gate_keys)
            total_present = sum(len((gate_coverage.get(gk) or {}).get("present") or []) for gk in gate_keys)
            total_missing = sum(len((gate_coverage.get(gk) or {}).get("missing") or []) for gk in gate_keys)

            summary = {
                "metrics_required": int(total_required),
                "metrics_present": int(total_present),
                "metrics_missing": int(total_missing),
                "metrics_present_via_alias": int(status_counts_ext["present_via_alias"]),
                "alias_conflicts_detected": int(status_counts_ext["alias_conflicts"]),
                "unmapped_related_detected": int(status_counts_ext["unmapped_related_detected"]),
            }

            qc_summary = {
                "qc_mode": str(qc_mode),
                "ignored_count": int(len(ignored or [])),
            }

            recency_common = _soe_v0_2_recency_from_metric_status(metrics_sorted, metric_status)
            per_metric_rec = {
                mk: {
                    "timestamp_used": (recency_common.get("per_metric", {}).get(mk) or {}).get("timestamp_used"),
                    "timestamp_value": (recency_common.get("per_metric", {}).get(mk) or {}).get("timestamp_value"),
                }
                for mk in metrics_sorted
            }
            recency = {"per_metric": per_metric_rec, "batch": recency_common.get("batch")}

            metrics_present = sorted([mk for mk in metrics_sorted if (metric_status.get(mk) or {}).get("status") in ("present", "present_but_non_numeric")])
            metrics_missing = sorted([mk for mk in metrics_sorted if mk not in metrics_present])

            coverage = {
                "molecule_id": int(molecule_id),
                "batch_ids": [int(x) for x in batch_ids],
                "decision": str(decision_key),
                "metrics_referenced": metrics_sorted,
                "metrics_present": metrics_present,
                "metrics_missing": metrics_missing,
            }
        else:
            batch_id = int((config or {}).get("batch_id") or 0)
            counts = {"present": 0, "missing": 0, "present_but_ignored": 0, "present_but_non_numeric": 0}
            for mk in metrics_sorted:
                st = (metric_status.get(mk) or {}).get("status")
                if st in counts:
                    counts[st] += 1

            gates_total = len(gate_keys)
            cov_sat = sum(1 for gk in gate_keys if bool((gate_coverage.get(gk) or {}).get("satisfied")))

            summary = {
                "metrics": {
                    "referenced_total": len(metrics_sorted),
                    "present": counts["present"],
                    "missing": counts["missing"],
                    "present_but_ignored": counts["present_but_ignored"],
                    "present_but_non_numeric": counts["present_but_non_numeric"],
                    "present_via_alias": int(status_counts_ext["present_via_alias"]),
                },
                "gates": {
                    "total": gates_total,
                    "coverage_satisfied": int(cov_sat),
                    "coverage_unsatisfied": int(gates_total - cov_sat),
                },
                "alias_mismatches": {
                    "unmapped_related_detected": int(status_counts_ext["unmapped_related_detected"]),
                    "conflicts_detected": int(status_counts_ext["alias_conflicts"]),
                },
            }

            qc_counts = {"approved": 0, "unreviewed": 0, "rejected": 0, "quarantined": 0, "unknown": 0}
            for mk, ev in sorted((used_by_metric or {}).items(), key=lambda kv: str(kv[0])):
                qs = getattr(ev, "qc_status", None)
                qs = str(qs) if qs is not None else "unknown"
                if qs not in qc_counts:
                    qs = "unknown"
                qc_counts[qs] += 1
            qc_summary = {"selected": qc_counts, "qc_mode": qc_mode, "notes": []}

            recency = _soe_v0_2_recency_from_metric_status(metrics_sorted, metric_status)

            metrics_present = sorted([mk for mk in metrics_sorted if (metric_status.get(mk) or {}).get("status") in ("present", "present_but_non_numeric")])
            metrics_missing = sorted([mk for mk in metrics_sorted if mk not in metrics_present])

            coverage = {
                "batch_id": int(batch_id),
                "decision": str(decision_key),
                "metrics_referenced": metrics_sorted,
                "metrics_present": metrics_present,
                "metrics_missing": metrics_missing,
            }

        return {
            "requirements": {"by_gate": requirements_by_gate},
            "metric_status": metric_status,
            "gate_coverage": gate_coverage,
            "summary": summary,
            "qc_summary": qc_summary,
            "recency": recency,
            "coverage": coverage,
        }

    if schema_version == "0.3":
        policy_body = (config or {}).get("policy_body") or {}
        ignored = (config or {}).get("ignored") or []
        qc_mode = str((config or {}).get("qc_mode") or "")
        as_of_ts = (config or {}).get("as_of_ts")
        dt_asof = parse_iso(as_of_ts) if as_of_ts else None
        alias_to_canonical = _build_alias_to_canonical(policy_body)
        referenced_metrics = _referenced_metrics_from_policy(policy_body)
        if scope_kind == "molecule":
            batch_ids = _dedupe_preserve_order_ints((config or {}).get("batch_ids") or [])
            rows = _fetch_v0_3_measurement_rows_for_batches(db, batch_ids=batch_ids)
        else:
            batch_id = int((config or {}).get("batch_id") or 0)
            rows = _fetch_v0_3_measurement_rows_for_batches(db, batch_ids=[int(batch_id)])
        ignored_by_metric = _ignored_by_metric_map(ignored)
        accept_qc = _build_qc_acceptor(policy_body, qc_mode)
        grouped = _group_rows_for_soe_v0_3(rows=rows, alias_to_canonical=alias_to_canonical, dt_asof=dt_asof)
        evidence_summary = _build_evidence_summary_v0_3(
            referenced_metrics=referenced_metrics,
            grouped=grouped,
            ignored_by_metric=ignored_by_metric,
            accept_qc=accept_qc,
        )
        if scope_kind == "molecule":
            batch_ids = _dedupe_preserve_order_ints((config or {}).get("batch_ids") or [])
            molecule_id = int((config or {}).get("molecule_id") or 0)
            return {
                "schema_version": "0.3",
                "molecule_id": int(molecule_id),
                "batch_ids": [int(x) for x in batch_ids],
                "evidence_summary": evidence_summary,
            }
        return {"schema_version": "0.3", "evidence_summary": evidence_summary}

    raise ValueError(f"Unsupported SoE schema_version: {schema_version}")


def build_soe_v0_2(
    db: Session,
    *,
    batch_id: int,
    decision_key: str,
    policy_body: Dict[str, Any],
    used_by_metric: Dict[str, Any],
    ignored: list[Any],
    warnings: list[Dict[str, Any]],
    qc_mode: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    return _build_soe_core(
        config=SoECoreConfig(
            schema_version="0.2",
            scope_kind="batch",
            db=db,
            batch_id=int(batch_id),
            decision_key=str(decision_key),
            policy_body=policy_body,
            used_by_metric=used_by_metric,
            ignored=ignored,
            warnings=warnings,
            qc_mode=str(qc_mode),
            context=context,
        )
    )


def build_soe_v0_2_molecule(
    db: Session,
    *,
    molecule_id: int,
    batch_ids: List[int],
    decision_key: str,
    policy_body: Dict[str, Any],
    used_by_metric: Dict[str, Any],
    ignored: list[Any],
    warnings: list[Dict[str, Any]],
    qc_mode: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Additive SoE schema v0.2 for molecule scope (aggregated over batches)."""
    return _build_soe_core(
        config=SoECoreConfig(
            schema_version="0.2",
            scope_kind="molecule",
            db=db,
            molecule_id=int(molecule_id),
            batch_ids=list(batch_ids or []),
            decision_key=str(decision_key),
            policy_body=policy_body,
            used_by_metric=used_by_metric,
            ignored=ignored,
            warnings=warnings,
            qc_mode=str(qc_mode),
            context=context,
        )
    )


def build_soe_v0_3(
    db: Session,
    *,
    batch_id: int,
    as_of_ts: Optional[str],
    qc_mode: str,
    policy_body: Dict[str, Any],
    used_by_metric: Dict[str, Any],
    ignored: list[Any],
) -> Dict[str, Any]:
    """Additive SoE schema v0.3.

    Evidence summary is computed deterministically from DB measurements + selector outputs.
    """

    return _build_soe_core(
        config=SoECoreConfig(
            schema_version="0.3",
            scope_kind="batch",
            db=db,
            batch_id=int(batch_id),
            as_of_ts=as_of_ts,
            qc_mode=str(qc_mode),
            policy_body=policy_body,
            used_by_metric=used_by_metric,
            ignored=ignored,
        )
    )


def build_soe_v0_3_molecule(
    db: Session,
    *,
    molecule_id: int,
    batch_ids: List[int],
    as_of_ts: Optional[str],
    qc_mode: str,
    policy_body: Dict[str, Any],
    used_by_metric: Dict[str, Any],
    ignored: list[Any],
) -> Dict[str, Any]:
    """Additive SoE schema v0.3 for molecule scope (aggregated over batches)."""

    return _build_soe_core(
        config=SoECoreConfig(
            schema_version="0.3",
            scope_kind="molecule",
            db=db,
            molecule_id=int(molecule_id),
            batch_ids=list(batch_ids or []),
            as_of_ts=as_of_ts,
            qc_mode=str(qc_mode),
            policy_body=policy_body,
            used_by_metric=used_by_metric,
            ignored=ignored,
        )
    )
