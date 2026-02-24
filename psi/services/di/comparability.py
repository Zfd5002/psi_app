"""DI Evidence comparability + QC coherence diagnostics.

Governance goals:
- Deterministic, additive diagnostics (no scoring, no gate overrides)
- No DB schema changes

Candidate measurement universe (per metric_key):
- apply metric alias canonicalization
- apply as_of_ts filtering (exclude produced after as_of_ts)
- exclude ignore_for_model measurements
- DO NOT filter by QC acceptance (we need QC incoherence visibility)

Emits:
- comparability.metric_level[] flags (mixed_method, unit_inconsistent)
- comparability.qc_coherence[] flags (qc_inconsistent)
- comparability.summary counts
- confidence_degradation (triggered iff any high-severity flags)

All lists are deterministically ordered.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from psi.core.measurement_schema import measurement_all_cols, measurement_cols
from psi.core.models import MeasurementQC
from psi.services.di.util import parse_iso, qc_status_from_flag


_SEVERITY_ORDER = {"high": 0, "moderate": 1, "low": 2}


def _norm_str(x: Any) -> str:
    if x is None:
        return "unknown"
    s = str(x).strip()
    return s if s else "unknown"


import datetime as _dt


def _canonical_method_signature(*, method: Any, producer: Any, producer_version: Any) -> str:
    # Deterministic, drift-resistant signature (exclude machine-local source_path by design).
    m = _norm_str(method)
    p = _norm_str(producer)
    pv = _norm_str(producer_version)
    return f"{m}|{p}|{pv}"


def _issue_action(policy_body: Dict[str, Any], issue: str) -> str:
    # warn|block; default warn
    rules = policy_body.get("comparability_rules") if isinstance(policy_body, dict) else None
    if isinstance(rules, dict):
        v = rules.get(issue)
        if isinstance(v, str) and v.strip().lower() in ("warn", "block"):
            return v.strip().lower()
    return "warn"


def compute_comparability(
    db: Session,
    *,
    batch_id: int,
    as_of_ts: Optional[str],
    metric_alias_map: Dict[str, List[str]],
    policy_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute comparability + qc coherence diagnostics for a batch.

    Returns a dict with keys:
      - comparability (top-level output object)
      - confidence_degradation (top-level output object)
      - readiness_additions: {"assumptions": [...], "blocking_reasons": [...]}
    """

    cols = measurement_cols(db)
    _ = measurement_all_cols(db)  # warm reflection cache

    record_fk = cols["record_fk"]
    name_col = cols["name"]
    id_col = cols["id"] or "id"

    ignore_col = cols.get("ignore_for_model")
    produced_col = cols.get("produced_at")
    created_col = cols.get("created_at")
    updated_col = cols.get("updated_at")

    unit_col = cols.get("unit")
    qc_flag_col = cols.get("qc_flag")

    # Method signature fields (may be absent in older DBs; treat missing as unknown)
    method_col = cols.get("method") or "method"
    producer_col = cols.get("producer") or "producer"
    producer_version_col = cols.get("producer_version") or "producer_version"

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

    # MeasurementQC map (if table present/populated)
    mids: List[int] = []
    for r in rows:
        v = r.get(id_col) if id_col in r else r.get("id")
        try:
            if v is not None:
                mids.append(int(v))
        except Exception:
            continue

    qc_map: Dict[int, str] = {}
    if mids:
        for mq in db.query(MeasurementQC).filter(MeasurementQC.measurement_id.in_(mids)).all():
            if mq.measurement_id is not None and mq.status:
                qc_map[int(mq.measurement_id)] = str(mq.status)

    dt_asof = parse_iso(as_of_ts) if as_of_ts else None

    # alias → canonical
    alias_to_canonical: Dict[str, str] = {}
    for canon, aliases in (metric_alias_map or {}).items():
        for a in aliases or []:
            alias_to_canonical[str(a)] = str(canon)

    grouped: Dict[str, List[Dict[str, Any]]] = {}

    def _row_dt(r: Dict[str, Any]) -> Optional[_dt.datetime]:
        dp = parse_iso(str(r.get(produced_col))) if produced_col and r.get(produced_col) is not None else None
        dc = parse_iso(str(r.get(created_col) or r.get(updated_col))) if (created_col or updated_col) and (r.get(created_col) is not None or r.get(updated_col) is not None) else None
        return dp or dc

    # Build candidate universe per metric_key
    for r in rows:
        mk_raw = r.get(name_col)
        mk = str(mk_raw).strip() if mk_raw is not None else ""
        if not mk:
            continue
        canon = alias_to_canonical.get(mk, mk)

        # exclude ignore_for_model
        if ignore_col and int(r.get(ignore_col) or 0) == 1:
            continue

        # as_of exclusion
        if dt_asof is not None:
            chk = _row_dt(r)
            if chk is not None and chk > dt_asof:
                continue

        grouped.setdefault(canon, []).append(r)

    metric_level: List[Dict[str, Any]] = []
    qc_coherence: List[Dict[str, Any]] = []

    # For readiness modifications (strings only; keep readiness schema stable)
    readiness_assumptions: List[str] = []
    readiness_blocking_reasons: List[str] = []

    confidence_reasons: List[Dict[str, Any]] = []

    for metric_key in sorted(grouped.keys()):
        rs = grouped.get(metric_key) or []
        if not rs:
            continue

        # Mixed method detection
        sigs = set()
        sig_list: List[str] = []
        for r in rs:
            sig = _canonical_method_signature(
                method=r.get(method_col),
                producer=r.get(producer_col),
                producer_version=r.get(producer_version_col),
            )
            if sig not in sigs:
                sigs.add(sig)
                sig_list.append(sig)
        sig_list = sorted(sig_list)
        if len(sig_list) > 1:
            issue = "mixed_method"
            severity = "moderate"
            metric_level.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "methods_detected": sig_list,
                    "severity": severity,
                }
            )

        # Unit inconsistency detection (severity escalation)
        units_seen: List[str] = []
        units_set = set()
        for r in rs:
            u = _norm_str(r.get(unit_col) if unit_col else None)
            if u not in units_set:
                units_set.add(u)
                units_seen.append(u)
        units_seen = sorted(units_seen)
        known = sorted([u for u in units_seen if u != "unknown"])
        has_unknown = "unknown" in units_seen
        if len(known) >= 2:
            issue = "unit_inconsistent"
            severity = "high"
            metric_level.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "units_detected": units_seen,
                    "severity": severity,
                }
            )
        elif len(known) == 1 and has_unknown:
            issue = "unit_inconsistent"
            severity = "moderate"
            metric_level.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "units_detected": units_seen,
                    "severity": severity,
                }
            )

        # QC coherence detection (across candidate universe)
        states_set = set()
        states: List[str] = []
        for r in rs:
            v = r.get(id_col) if id_col in r else r.get("id")
            try:
                mid = int(v)
            except Exception:
                continue
            qc_status = qc_map.get(mid) or qc_status_from_flag(r.get(qc_flag_col) if qc_flag_col else None)
            qc_status = str(qc_status).strip() if qc_status is not None else "unknown"
            if qc_status not in states_set:
                states_set.add(qc_status)
                states.append(qc_status)
        states = sorted(states)
        if len(states) > 1:
            issue = "qc_inconsistent"
            severity = "high"
            qc_coherence.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "states_detected": states,
                    "severity": severity,
                }
            )

    # Deterministic ordering of flag lists
    metric_level.sort(key=lambda x: (str(x.get("metric_key") or ""), str(x.get("issue") or "")))
    qc_coherence.sort(key=lambda x: (str(x.get("metric_key") or ""), str(x.get("issue") or "")))

    # Summary + confidence degradation
    all_flags: List[Dict[str, Any]] = []
    all_flags.extend(metric_level)
    all_flags.extend(qc_coherence)

    high_flags: List[Tuple[str, str, str]] = []
    for f in all_flags:
        sev = str(f.get("severity") or "").strip().lower()
        if sev == "high":
            issue = str(f.get("issue") or "")
            mk = str(f.get("metric_key") or "")
            high_flags.append((issue, mk, sev))

    for (issue, mk, sev) in sorted(high_flags, key=lambda t: (t[0], t[1], t[2])):
        confidence_reasons.append({"kind": issue, "metric_key": mk, "severity": sev})

    triggered = bool(confidence_reasons)

    # Readiness additions
    if triggered:
        # Add assumptions for high severity flags (structured strings; deterministic)
        for r in confidence_reasons:
            readiness_assumptions.append(f"comparability:{r['kind']}:{r['metric_key']}:{r['severity']}")

    # Blocking behavior depends on policy rules (warn|block) and high severity only
    if triggered:
        for r in confidence_reasons:
            action = _issue_action(policy_body, str(r.get("kind") or ""))
            if action == "block":
                readiness_blocking_reasons.append(
                    f"Comparability block: {r['kind']} for metric {r['metric_key']} (severity={r['severity']})"
                )

    readiness_assumptions = sorted(set(readiness_assumptions))
    readiness_blocking_reasons = sorted(set(readiness_blocking_reasons))

    comp_obj = {
        "metric_level": metric_level,
        "qc_coherence": qc_coherence,
        "summary": {
            "total_flags": int(len(metric_level) + len(qc_coherence)),
            "high_severity_count": int(sum(1 for f in all_flags if str(f.get("severity") or "").strip().lower() == "high")),
        },
    }

    conf_obj = {"triggered": bool(triggered), "reasons": confidence_reasons}

    return {
        "comparability": comp_obj,
        "confidence_degradation": conf_obj,
        "readiness_additions": {
            "assumptions": readiness_assumptions,
            "blocking_reasons": readiness_blocking_reasons,
        },
    }


def compute_comparability_for_batches(
    db: Session,
    *,
    batch_ids: List[int],
    as_of_ts: Optional[str],
    metric_alias_map: Dict[str, List[str]],
    policy_body: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute comparability + qc coherence diagnostics for a set of batches (molecule scope)."""

    batch_ids = [int(x) for x in batch_ids if str(x).isdigit() and int(x) > 0]
    batch_ids = sorted(list(set(batch_ids)))
    if not batch_ids:
        return {
            "comparability": {"metric_level": [], "qc_coherence": [], "summary": {"total_flags": 0, "high_severity_count": 0}},
            "confidence_degradation": {"triggered": False, "reasons": []},
            "readiness_additions": {"assumptions": [], "blocking_reasons": []},
        }

    cols = measurement_cols(db)
    _ = measurement_all_cols(db)

    record_fk = cols["record_fk"]
    name_col = cols["name"]
    id_col = cols["id"] or "id"

    ignore_col = cols.get("ignore_for_model")
    produced_col = cols.get("produced_at")
    created_col = cols.get("created_at")
    updated_col = cols.get("updated_at")

    unit_col = cols.get("unit")
    qc_flag_col = cols.get("qc_flag")

    method_col = cols.get("method") or "method"
    producer_col = cols.get("producer") or "producer"
    producer_version_col = cols.get("producer_version") or "producer_version"

    q = text(
        f"""
        SELECT
          dm.*,
          dr.id as _dr_id
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE dr.batch_id IN :bids
        ORDER BY dm.{id_col} ASC
        """
    ).bindparams(bindparam("bids", expanding=True))
    rows = db.execute(q, {"bids": list(batch_ids)}).mappings().all()

    mids: List[int] = []
    for r in rows:
        v = r.get(id_col) if id_col in r else r.get("id")
        try:
            if v is not None:
                mids.append(int(v))
        except Exception:
            continue

    qc_map: Dict[int, str] = {}
    if mids:
        for mq in db.query(MeasurementQC).filter(MeasurementQC.measurement_id.in_(mids)).all():
            if mq.measurement_id is not None and mq.status:
                qc_map[int(mq.measurement_id)] = str(mq.status)

    dt_asof = parse_iso(as_of_ts) if as_of_ts else None

    alias_to_canonical: Dict[str, str] = {}
    for canon, aliases in (metric_alias_map or {}).items():
        for a in aliases or []:
            alias_to_canonical[str(a)] = str(canon)

    grouped: Dict[str, List[Dict[str, Any]]] = {}

    def _row_dt(r: Dict[str, Any]) -> Optional[_dt.datetime]:
        dp = parse_iso(str(r.get(produced_col))) if produced_col and r.get(produced_col) is not None else None
        dc = parse_iso(str(r.get(created_col) or r.get(updated_col))) if (created_col or updated_col) and (r.get(created_col) is not None or r.get(updated_col) is not None) else None
        return dp or dc

    for r in rows:
        mk_raw = r.get(name_col)
        mk = str(mk_raw).strip() if mk_raw is not None else ""
        if not mk:
            continue
        canon = alias_to_canonical.get(mk, mk)

        if ignore_col and int(r.get(ignore_col) or 0) == 1:
            continue

        if dt_asof is not None:
            chk = _row_dt(r)
            if chk is not None and chk > dt_asof:
                continue

        grouped.setdefault(canon, []).append(r)

    metric_level: List[Dict[str, Any]] = []
    qc_coherence: List[Dict[str, Any]] = []

    readiness_assumptions: List[str] = []
    readiness_blocking_reasons: List[str] = []

    confidence_reasons: List[Dict[str, Any]] = []

    for metric_key in sorted(grouped.keys()):
        rs = grouped.get(metric_key) or []
        if not rs:
            continue

        sigs = set()
        sig_list: List[str] = []
        for r in rs:
            sig = _canonical_method_signature(
                method=r.get(method_col),
                producer=r.get(producer_col),
                producer_version=r.get(producer_version_col),
            )
            if sig not in sigs:
                sigs.add(sig)
                sig_list.append(sig)
        sig_list = sorted(sig_list)
        if len(sig_list) > 1:
            issue = "mixed_method"
            severity = "moderate"
            metric_level.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "methods_detected": sig_list,
                    "severity": severity,
                }
            )

        units_seen: List[str] = []
        units_set = set()
        for r in rs:
            u = _norm_str(r.get(unit_col) if unit_col else None)
            if u not in units_set:
                units_set.add(u)
                units_seen.append(u)
        units_seen = sorted(units_seen)
        known = sorted([u for u in units_seen if u != "unknown"])
        has_unknown = "unknown" in units_seen
        if len(known) >= 2:
            issue = "unit_inconsistent"
            severity = "high"
            metric_level.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "units_detected": units_seen,
                    "severity": severity,
                }
            )
        elif len(known) == 1 and has_unknown:
            issue = "unit_inconsistent"
            severity = "moderate"
            metric_level.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "units_detected": units_seen,
                    "severity": severity,
                }
            )

        states_set = set()
        states: List[str] = []
        for r in rs:
            v = r.get(id_col) if id_col in r else r.get("id")
            try:
                mid = int(v)
            except Exception:
                continue
            qc_status = qc_map.get(mid) or qc_status_from_flag(r.get(qc_flag_col) if qc_flag_col else None)
            qc_status = str(qc_status).strip() if qc_status is not None else "unknown"
            if qc_status not in states_set:
                states_set.add(qc_status)
                states.append(qc_status)
        states = sorted(states)
        if len(states) > 1:
            issue = "qc_inconsistent"
            severity = "high"
            qc_coherence.append(
                {
                    "metric_key": str(metric_key),
                    "issue": issue,
                    "states_detected": states,
                    "severity": severity,
                }
            )

    metric_level.sort(key=lambda x: (str(x.get("metric_key") or ""), str(x.get("issue") or "")))
    qc_coherence.sort(key=lambda x: (str(x.get("metric_key") or ""), str(x.get("issue") or "")))

    all_flags: List[Dict[str, Any]] = []
    all_flags.extend(metric_level)
    all_flags.extend(qc_coherence)

    high_flags: List[Tuple[str, str, str]] = []
    for f in all_flags:
        sev = str(f.get("severity") or "").strip().lower()
        if sev == "high":
            issue = str(f.get("issue") or "")
            mk = str(f.get("metric_key") or "")
            high_flags.append((issue, mk, sev))

    for (issue, mk, sev) in sorted(high_flags, key=lambda t: (t[0], t[1], t[2])):
        confidence_reasons.append({"kind": issue, "metric_key": mk, "severity": sev})

    triggered = bool(confidence_reasons)

    if triggered:
        for r in confidence_reasons:
            readiness_assumptions.append(f"comparability:{r['kind']}:{r['metric_key']}:{r['severity']}")

    if triggered:
        for r in confidence_reasons:
            action = _issue_action(policy_body, str(r.get("kind") or ""))
            if action == "block":
                readiness_blocking_reasons.append(
                    f"Comparability block: {r['kind']} for metric {r['metric_key']} (severity={r['severity']})"
                )

    readiness_assumptions = sorted(set(readiness_assumptions))
    readiness_blocking_reasons = sorted(set(readiness_blocking_reasons))

    comp_obj = {
        "metric_level": metric_level,
        "qc_coherence": qc_coherence,
        "summary": {
            "total_flags": int(len(metric_level) + len(qc_coherence)),
            "high_severity_count": int(sum(1 for f in all_flags if str(f.get("severity") or "").strip().lower() == "high")),
        },
    }

    conf_obj = {"triggered": bool(triggered), "reasons": confidence_reasons}

    return {
        "comparability": comp_obj,
        "confidence_degradation": conf_obj,
        "readiness_additions": {
            "assumptions": readiness_assumptions,
            "blocking_reasons": readiness_blocking_reasons,
        },
    }
