"""DI enrichment helpers.

These are derived-only, reporting-focused structures. They must be:
- deterministic
- additive-only
- policy-derived (no hidden heuristics)

They MUST NOT change selection or evaluation semantics.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_cols


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


def _timestamp_used(produced_at: Optional[str], created_at: Optional[str]) -> Dict[str, Any]:
    dp = _parse_iso(produced_at)
    dc = _parse_iso(created_at)
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

    metrics_sorted = sorted(referenced_metrics)

    raw_keys = _fetch_batch_metric_keys_raw(db, batch_id=batch_id)

    ignored_by_metric: Dict[str, list[Any]] = {}
    for ig in ignored or []:
        try:
            mk = str(getattr(ig, "metric_key", "") or "").strip()
        except Exception:
            mk = ""
        if mk:
            ignored_by_metric.setdefault(mk, []).append(ig)

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

    gate_coverage: Dict[str, Any] = {}
    for gk in gate_keys:
        gd = gates.get(gk) or {}
        if not isinstance(gd, dict):
            gd = {}
        req_type = "require_all" if "require_all" in gd else ("require_any" if "require_any" in gd else "")
        req_list = gd.get("require_all") if "require_all" in gd else gd.get("require_any")
        req_list = req_list if isinstance(req_list, list) else []
        required = sorted([str(x) for x in req_list if str(x).strip()])

        present = []
        missing = []
        for m in required:
            st = (metric_status.get(m) or {}).get("status")
            if st in ("present", "present_but_non_numeric"):
                present.append(m)
            else:
                missing.append(m)

        satisfied = False
        if req_type == "require_all":
            satisfied = len(missing) == 0
        elif req_type == "require_any":
            satisfied = len(present) > 0

        gate_coverage[gk] = {
            "requirement_type": req_type,
            "required": required,
            "present": sorted(present),
            "missing": sorted(missing),
            "satisfied": bool(satisfied),
        }

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
            "present_via_alias": int(present_via_alias),
        },
        "gates": {
            "total": gates_total,
            "coverage_satisfied": int(cov_sat),
            "coverage_unsatisfied": int(gates_total - cov_sat),
        },
        "alias_mismatches": {
            "unmapped_related_detected": int(unmapped_related_detected),
            "conflicts_detected": int(alias_conflicts),
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
        dtv = _parse_iso(tv) if isinstance(tv, str) else None
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

    recency = {"per_metric": per_metric_rec, "batch": batch_rec}

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

    dt_asof = _parse_iso(as_of_ts) if as_of_ts else None

    # Canonicalize using policy alias map.
    alias_to_canonical: Dict[str, str] = {}
    for canon, aliases in ((policy_body or {}).get("metric_alias_map") or {}).items():
        for a in aliases or []:
            sa = str(a).strip()
            sc = str(canon).strip()
            if sa and sc:
                alias_to_canonical[sa] = sc

    # Metrics referenced by gates (stable scope for SoE summaries).
    referenced: set[str] = set()
    gates = (policy_body or {}).get("gates") or {}
    if isinstance(gates, dict):
        for gd in gates.values():
            if not isinstance(gd, dict):
                continue
            lst = gd.get("require_all") if isinstance(gd.get("require_all"), list) else gd.get("require_any")
            if isinstance(lst, list):
                for x in lst:
                    sx = str(x).strip()
                    if sx:
                        referenced.add(sx)

    referenced_metrics = sorted(referenced)

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
        WHERE dr.batch_id = :bid
        ORDER BY dm.{id_col} ASC
        """
    )
    rows = db.execute(q, {"bid": int(batch_id)}).mappings().all()

    # Build ignored breakdown from selector output (already deterministic ordering).
    ignored_by_metric: Dict[str, List[Any]] = {}
    for ig in ignored or []:
        try:
            mk = str(getattr(ig, "metric_key", "") or "").strip()
        except Exception:
            mk = ""
        if mk:
            ignored_by_metric.setdefault(mk, []).append(ig)

    # Pre-compute QC acceptability using the same policy QC modes definition.
    policy_qc = (policy_body or {}).get("qc_modes") or {}
    qc_conf = (policy_qc.get(qc_mode) or {}) if isinstance(policy_qc, dict) else {}
    accept = set(str(x) for x in (qc_conf.get("accept_statuses") or []))
    reject = set(str(x) for x in (qc_conf.get("reject_statuses") or []))
    treat_unreviewed_as = str(qc_conf.get("treat_unreviewed_as") or "accept")

    def qc_status_from_flag(raw: Any) -> str:
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

    def accept_qc(qs: str) -> bool:
        if qs in reject:
            return False
        if qs == "unreviewed" and str(qc_mode) == "strict":
            return False
        if qs in accept:
            return True
        # unknown: strict rejects; others accept
        if str(qc_mode) == "strict":
            return False
        return True

    # Group rows by canonical metric.
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        mk_raw = r.get("metric_key")
        mk = str(mk_raw).strip() if mk_raw is not None else ""
        if not mk:
            continue
        canon = alias_to_canonical.get(mk, mk)

        # Apply as-of exclusion consistent with selectors.
        if dt_asof is not None:
            dp = _parse_iso(r.get("produced_at"))
            dc = _parse_iso(r.get("created_at"))
            chk = dp or dc
            if chk is not None and chk > dt_asof:
                continue

        grouped.setdefault(canon, []).append(r)

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

            dp = _parse_iso(r.get("produced_at"))
            dc = _parse_iso(r.get("created_at"))
            chk = dp or dc
            if chk is not None:
                if latest_dt is None or chk > latest_dt:
                    latest_dt = chk

            if int(r.get("ignore_for_model") or 0) == 1:
                continue
            qs = qc_status_from_flag(r.get("qc_flag"))
            if accept_qc(qs):
                usable_count += 1

        igs = ignored_by_metric.get(mk) or []
        ignored_count = len(igs)
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
                "ignored_count": int(ignored_count),
                "latest_timestamp": latest_dt.isoformat() if latest_dt is not None else None,
                "methods_present": sorted(set(methods_present)),
                "units_present": sorted(set(units_present)),
                "ignore_reasons_breakdown": [
                    {"reason_key": rk, "count": int(breakdown[rk])} for rk in sorted(breakdown.keys())
                ],
            }
        )

    # Deterministic ordering by metric_key ASC (already in referenced_metrics order)
    return {"schema_version": "0.3", "evidence_summary": evidence_summary}


def derive_risk_flags_enriched(*, risk_flags: list[Dict[str, Any]], used_by_metric: Dict[str, Any], policy_body: Dict[str, Any]) -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    used_keys = set(str(k) for k in (used_by_metric or {}).keys())

    for rf in risk_flags or []:
        key = str((rf or {}).get("risk_flag") or (rf or {}).get("key") or "").strip()
        if not key:
            continue

        category = "other"
        severity = "low"
        related_metrics: list[str] = []
        explanation = str((rf or {}).get("detail") or (rf or {}).get("explanation") or key)

        if key in ("qc_uncertainty", "outlier_present"):
            category = "data_quality"
            severity = "moderate"
        elif key in ("method_incomparable",):
            category = "comparability"
            severity = "moderate"
        elif key in ("coverage_gap", "missing_required_metric"):
            category = "coverage"
            severity = "high"

        gates = (policy_body or {}).get("gates") or {}
        if isinstance(gates, dict):
            for gd in gates.values():
                if not isinstance(gd, dict):
                    continue
                lst = gd.get("require_all") if isinstance(gd.get("require_all"), list) else gd.get("require_any")
                if isinstance(lst, list):
                    for x in lst:
                        sx = str(x).strip()
                        if sx and sx in used_keys:
                            related_metrics.append(sx)
        related_metrics = sorted(set(related_metrics))

        out.append(
            {
                "key": key,
                "category": category,
                "severity": severity,
                "related_metrics": related_metrics,
                "explanation": explanation,
            }
        )

    sev_rank = {"high": 0, "moderate": 1, "low": 2}
    out = sorted(out, key=lambda x: (sev_rank.get(str((x or {}).get("severity") or "").strip().lower(), 9), str((x or {}).get("category") or ""), str((x or {}).get("key") or "")))
    return out


def coverage_fingerprint_payload(*, readiness: Dict[str, Any], gate_outcomes: Dict[str, Any]) -> Dict[str, Any]:
    r = readiness or {}
    cov = (r.get("coverage") or {}) if isinstance(r, dict) else {}
    comp = (r.get("comparability") or {}) if isinstance(r, dict) else {}
    return {
        "blockers": r.get("blockers") or [],
        "coverage": {
            "required_present": cov.get("required_present"),
            "required_total": cov.get("required_total"),
            "optional_present": cov.get("optional_present"),
            "optional_total": cov.get("optional_total"),
            "coverage_ratio": cov.get("coverage_ratio"),
        },
        "gate_outcomes": gate_outcomes or {},
        "comparability": {
            "method_incomparable_metrics": (comp.get("method_incomparable_metrics") or []),
            "notes": (comp.get("notes") or []),
        },
    }


def derive_suggestions(
    *,
    gate_outcomes: Dict[str, Any],
    readiness: Dict[str, Any],
    ignored: list[Any],
) -> list[Dict[str, Any]]:
    """Policy-derived, non-ranked suggestions.

    Derived only from missing evidence and ignore taxonomy.
    """

    suggestions: Dict[str, Dict[str, Any]] = {}

    # Missing metrics from gate_outcomes
    for gk, gi in (gate_outcomes or {}).items():
        _ = gk
        miss = (gi or {}).get("missing_metrics") or []
        if isinstance(miss, list):
            for mk in miss:
                smk = str(mk).strip()
                if not smk:
                    continue
                sid = f"missing_metric:{smk}"
                suggestions[sid] = {
                    "suggestion_id": sid,
                    "type": "missing_metric",
                    "rationale": "Metric required by policy but missing in selected evidence.",
                    "action_spec": {"metric_key": smk, "preferred_method": None, "required_unit": None},
                }

    # Method incomparability (from readiness.comparability)
    comp = (readiness or {}).get("comparability") or {}
    mi = comp.get("method_incomparable_metrics") if isinstance(comp, dict) else []
    if isinstance(mi, list):
        for mk in mi:
            smk = str(mk).strip()
            if not smk:
                continue
            sid = f"method_incomparable:{smk}"
            suggestions[sid] = {
                "suggestion_id": sid,
                "type": "method_incomparable",
                "rationale": "Evidence exists but is method-incomparable under policy; capture comparable method per SOP.",
                "action_spec": {"metric_key": smk, "preferred_method": None, "required_unit": None},
            }

    # Unit incompatibility (from ignored taxonomy)
    for ig in ignored or []:
        try:
            rk = str(getattr(ig, "reason_key", "") or "").strip()
            mk = str(getattr(ig, "metric_key", "") or "").strip()
        except Exception:
            rk, mk = "", ""
        if not mk:
            continue
        if rk == "unit_inconvertible":
            sid = f"unit_inconvertible:{mk}"
            suggestions[sid] = {
                "suggestion_id": sid,
                "type": "unit_inconvertible",
                "rationale": "Evidence exists but unit is not comparable/convertible under current policy constraints.",
                "action_spec": {"metric_key": mk, "preferred_method": None, "required_unit": None},
            }

    return [suggestions[k] for k in sorted(suggestions.keys())]
