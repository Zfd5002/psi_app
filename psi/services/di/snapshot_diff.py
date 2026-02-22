"""Deterministic DI DecisionSnapshot diff utilities.

This module is the shared, importable home for DI snapshot diff logic.

Governance notes:
- Read-only: does not mutate the DB.
- Deterministic: stable ordering; no timestamps.
- Derived-only: drift labels are computed only from signals embedded in snapshots.

Web and CLI must both import from here (no duplicated diff algorithms).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot
from psi.services.decisions import stable_json_dumps


def _json_load(text: str) -> Any:
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _canon(obj: Any) -> str:
    # Canonical string for deterministic set comparisons.
    return stable_json_dumps(obj)


def _sorted_unique(items: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for s in items:
        ss = str(s)
        if ss in seen:
            continue
        seen.add(ss)
        out.append(ss)
    return sorted(out)


def _dict_get(d: Dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


@dataclass(frozen=True)
class DriftResult:
    drift_label: str
    summary: Dict[str, Any]
    changes: Dict[str, Any]


def _extract_integrity(out: Dict[str, Any]) -> Dict[str, str]:
    prov = _as_dict(out.get("provenance"))
    integ = _as_dict(prov.get("integrity"))
    return {
        "snapshot_content_hash": str(integ.get("snapshot_content_hash") or ""),
        "evidence_fingerprint": str(integ.get("evidence_fingerprint") or ""),
    }


def _extract_used_tuples(out: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Return metric_key -> tuple-like dict (measurement_id, qc_status, unit, comparator).

    This is used only for deterministic diff rendering.
    """
    soe = _as_dict(out.get("state_of_evidence"))
    used = _as_dict(soe.get("used"))
    by_metric: Dict[str, Dict[str, str]] = {}
    for mk in sorted([str(k) for k in used.keys()]):
        ev = used.get(mk)
        if isinstance(ev, dict):
            by_metric[mk] = {
                "measurement_id": str(ev.get("measurement_id") or ""),
                "qc_status": str(ev.get("qc_status") or ""),
                "unit": str(ev.get("unit") or ""),
                "comparator": str(ev.get("comparator") or ""),
            }
        else:
            by_metric[mk] = {
                "measurement_id": str(getattr(ev, "measurement_id", "") or ""),
                "qc_status": str(getattr(ev, "qc_status", "") or ""),
                "unit": str(getattr(ev, "unit", "") or ""),
                "comparator": str(getattr(ev, "comparator", "") or ""),
            }
    return by_metric


def _evidence_metric_deltas(a: Dict[str, Dict[str, str]], b: Dict[str, Dict[str, str]]) -> Dict[str, Any] | None:
    a_keys = set(a.keys())
    b_keys = set(b.keys())
    added = sorted(list(b_keys - a_keys))
    removed = sorted(list(a_keys - b_keys))
    changed: Dict[str, Any] = {}
    for mk in sorted(list(a_keys & b_keys)):
        aa = a.get(mk) or {}
        bb = b.get(mk) or {}
        if _canon(aa) != _canon(bb):
            # stable, explicit field diffs
            d: Dict[str, Any] = {}
            for k in ("measurement_id", "qc_status", "unit", "comparator"):
                if str(aa.get(k) or "") != str(bb.get(k) or ""):
                    d[k] = {"from": aa.get(k) or "", "to": bb.get(k) or ""}
            if d:
                changed[mk] = d
    if not added and not removed and not changed:
        return None
    return {"added": added, "removed": removed, "changed": changed}


def compute_snapshot_diff_struct(
    *,
    out1: Dict[str, Any],
    in1: Dict[str, Any],
    out2: Dict[str, Any],
    in2: Dict[str, Any],
) -> DriftResult:
    """Pure function: diff two parsed DI snapshot payloads."""

    # --- extract key signals (prefer outputs_json; fall back to inputs_json) ---
    pol1 = _as_dict(out1.get("policy"))
    pol2 = _as_dict(out2.get("policy"))

    sem1 = str(pol1.get("policy_semantics_hash") or in1.get("policy_semantics_hash") or "")
    sem2 = str(pol2.get("policy_semantics_hash") or in2.get("policy_semantics_hash") or "")

    pkg1 = str(pol1.get("policy_package_hash") or in1.get("policy_package_hash") or "")
    pkg2 = str(pol2.get("policy_package_hash") or in2.get("policy_package_hash") or "")

    eng1 = _as_dict(out1.get("engine"))
    eng2 = _as_dict(out2.get("engine"))

    prov1 = _as_dict(out1.get("provenance"))
    prov2 = _as_dict(out2.get("provenance"))

    cat1 = _as_dict(_dict_get(prov1, "experiment_catalog") or {})
    cat2 = _as_dict(_dict_get(prov2, "experiment_catalog") or {})
    cat_hash1 = str(cat1.get("catalog_hash") or in1.get("catalog_hash") or "")
    cat_hash2 = str(cat2.get("catalog_hash") or in2.get("catalog_hash") or "")

    qc_mode1 = str(prov1.get("qc_mode") or in1.get("qc_mode") or "")
    qc_mode2 = str(prov2.get("qc_mode") or in2.get("qc_mode") or "")

    sel_sem1 = str(prov1.get("selection_semantics_version") or in1.get("selection_semantics_version") or "")
    sel_sem2 = str(prov2.get("selection_semantics_version") or in2.get("selection_semantics_version") or "")

    integrity1 = _extract_integrity(out1)
    integrity2 = _extract_integrity(out2)

    # --- key DI fields ---
    readiness1 = _as_dict(out1.get("readiness"))
    readiness2 = _as_dict(out2.get("readiness"))

    gate_outcomes1 = _as_dict(out1.get("gate_outcomes"))
    gate_outcomes2 = _as_dict(out2.get("gate_outcomes"))

    cov_fp1 = str(out1.get("coverage_fingerprint") or "")
    cov_fp2 = str(out2.get("coverage_fingerprint") or "")

    # evidence ids (DI runner emits measurement_ids_used)
    mids1 = [int(x) for x in (_as_list(out1.get("measurement_ids_used")) or []) if str(x).isdigit()]
    mids2 = [int(x) for x in (_as_list(out2.get("measurement_ids_used")) or []) if str(x).isdigit()]
    mids1 = sorted(set(mids1))
    mids2 = sorted(set(mids2))

    used1 = _extract_used_tuples(out1)
    used2 = _extract_used_tuples(out2)

    changes: Dict[str, Any] = {}

    def _diff_simple(a: Any, b: Any) -> Optional[Dict[str, Any]]:
        if _canon(a) == _canon(b):
            return None
        return {"from": a, "to": b}

    # readiness
    readiness_changes: Dict[str, Any] = {}
    for k in ("state",):
        d = _diff_simple(readiness1.get(k), readiness2.get(k))
        if d is not None:
            readiness_changes[k] = d

    # readiness.coverage
    cov1 = _as_dict(readiness1.get("coverage"))
    cov2 = _as_dict(readiness2.get("coverage"))
    cov_changes: Dict[str, Any] = {}
    for k in ("required_present", "required_total", "optional_present", "optional_total", "coverage_ratio"):
        d = _diff_simple(cov1.get(k), cov2.get(k))
        if d is not None:
            cov_changes[k] = d
    if cov_changes:
        readiness_changes["coverage"] = cov_changes

    # readiness.qc_confidence
    qc1 = _as_dict(readiness1.get("qc_confidence"))
    qc2 = _as_dict(readiness2.get("qc_confidence"))
    qc_changes: Dict[str, Any] = {}
    for k in ("qc_mode", "reviewed_required_present", "unreviewed_required_present"):
        d = _diff_simple(qc1.get(k), qc2.get(k))
        if d is not None:
            qc_changes[k] = d
    notes1 = _sorted_unique([str(x) for x in (_as_list(qc1.get("notes")) or []) if str(x).strip()])
    notes2 = _sorted_unique([str(x) for x in (_as_list(qc2.get("notes")) or []) if str(x).strip()])
    if notes1 != notes2:
        qc_changes["notes"] = {
            "removed": [x for x in notes1 if x not in set(notes2)],
            "added": [x for x in notes2 if x not in set(notes1)],
        }
    if qc_changes:
        readiness_changes["qc_confidence"] = qc_changes

    # readiness.comparability
    comp1 = _as_dict(readiness1.get("comparability"))
    comp2 = _as_dict(readiness2.get("comparability"))
    comp_changes: Dict[str, Any] = {}
    mic1 = _sorted_unique([str(x) for x in (_as_list(comp1.get("method_incomparable_metrics")) or []) if str(x).strip()])
    mic2 = _sorted_unique([str(x) for x in (_as_list(comp2.get("method_incomparable_metrics")) or []) if str(x).strip()])
    if mic1 != mic2:
        comp_changes["method_incomparable_metrics"] = {
            "removed": [x for x in mic1 if x not in set(mic2)],
            "added": [x for x in mic2 if x not in set(mic1)],
        }
    n1 = _sorted_unique([str(x) for x in (_as_list(comp1.get("notes")) or []) if str(x).strip()])
    n2 = _sorted_unique([str(x) for x in (_as_list(comp2.get("notes")) or []) if str(x).strip()])
    if n1 != n2:
        comp_changes["notes"] = {"removed": [x for x in n1 if x not in set(n2)], "added": [x for x in n2 if x not in set(n1)]}
    if comp_changes:
        readiness_changes["comparability"] = comp_changes

    # readiness.blockers (full structural diff)
    def _blocker_key(b: Dict[str, Any]) -> str:
        bb = _as_dict(b)
        return _canon(
            {
                "key": str(bb.get("key") or ""),
                "severity": str(bb.get("severity") or ""),
                "metrics": sorted([str(x) for x in (_as_list(bb.get("metrics")) or [])]),
                "gates": sorted([str(x) for x in (_as_list(bb.get("gates")) or [])]),
                "explanation": str(bb.get("explanation") or ""),
            }
        )

    bl1 = [_blocker_key(b) for b in (_as_list(readiness1.get("blockers")) or [])]
    bl2 = [_blocker_key(b) for b in (_as_list(readiness2.get("blockers")) or [])]
    bl1 = sorted(set(bl1))
    bl2 = sorted(set(bl2))
    if bl1 != bl2:
        readiness_changes["blockers"] = {
            "removed": [json.loads(x) for x in bl1 if x not in set(bl2)],
            "added": [json.loads(x) for x in bl2 if x not in set(bl1)],
        }

    if readiness_changes:
        changes["readiness"] = readiness_changes

    # gate_outcomes
    go_changes: Dict[str, Any] = {}
    gokeys = sorted(set([str(k) for k in gate_outcomes1.keys()] + [str(k) for k in gate_outcomes2.keys()]))
    for gk in gokeys:
        g1 = _as_dict(gate_outcomes1.get(gk))
        g2 = _as_dict(gate_outcomes2.get(gk))
        if not g1 and g2:
            go_changes[gk] = {"added": g2}
            continue
        if g1 and not g2:
            go_changes[gk] = {"removed": g1}
            continue
        gchg: Dict[str, Any] = {}
        for k in ("status",):
            d = _diff_simple(g1.get(k), g2.get(k))
            if d is not None:
                gchg[k] = d
        for lk in ("required_metrics", "present_metrics", "missing_metrics", "qc_notes"):
            l1 = _sorted_unique([str(x) for x in (_as_list(g1.get(lk)) or []) if str(x).strip()])
            l2 = _sorted_unique([str(x) for x in (_as_list(g2.get(lk)) or []) if str(x).strip()])
            if l1 != l2:
                gchg[lk] = {"removed": [x for x in l1 if x not in set(l2)], "added": [x for x in l2 if x not in set(l1)]}
        if gchg:
            go_changes[gk] = gchg
    if go_changes:
        changes["gate_outcomes"] = go_changes

    # fingerprints/hashes
    hash_changes: Dict[str, Any] = {}
    if cov_fp1 != cov_fp2:
        hash_changes["coverage_fingerprint"] = {"from": cov_fp1, "to": cov_fp2}
    if sem1 != sem2:
        hash_changes["policy_semantics_hash"] = {"from": sem1, "to": sem2}
    if pkg1 != pkg2:
        hash_changes["policy_package_hash"] = {"from": pkg1, "to": pkg2}
    if cat_hash1 != cat_hash2:
        hash_changes["catalog_hash"] = {"from": cat_hash1, "to": cat_hash2}
    if hash_changes:
        changes["hashes"] = hash_changes

    # integrity hashes
    integ_changes: Dict[str, Any] = {}
    for k in ("snapshot_content_hash", "evidence_fingerprint"):
        if str(integrity1.get(k) or "") != str(integrity2.get(k) or ""):
            integ_changes[k] = {"from": integrity1.get(k) or "", "to": integrity2.get(k) or ""}
    if integ_changes:
        changes["integrity"] = integ_changes

    # measurement ids used
    if mids1 != mids2:
        changes["measurement_ids_used"] = {
            "removed": [x for x in mids1 if x not in set(mids2)],
            "added": [x for x in mids2 if x not in set(mids1)],
        }

    # evidence deltas by metric
    ev_delta = _evidence_metric_deltas(used1, used2)
    if ev_delta is not None:
        changes["evidence_by_metric"] = ev_delta

    # engine/provenance identifiers
    ident_changes: Dict[str, Any] = {}
    for k in ("engine_id", "schema_version", "selector_version", "evaluator_version"):
        d = _diff_simple(eng1.get(k), eng2.get(k))
        if d is not None:
            ident_changes[k] = d
    d = _diff_simple(sel_sem1, sel_sem2)
    if d is not None:
        ident_changes["selection_semantics_version"] = d
    d = _diff_simple(qc_mode1, qc_mode2)
    if d is not None:
        ident_changes["qc_mode"] = d
    if ident_changes:
        changes["identifiers"] = ident_changes

    # --- drift classification (derived-only, deterministic) ---
    # precedence:
    # policy_drift > structural_drift > qc_drift > data_drift > no_change

    if not changes:
        drift = "no_change"
    else:
        policy_changed = (sem1 != sem2) or (pkg1 != pkg2) or (cat_hash1 != cat_hash2)
        structural_changed = ("identifiers" in changes) and any(
            k in changes["identifiers"]
            for k in ("engine_id", "schema_version", "selector_version", "evaluator_version", "selection_semantics_version")
        )

        qc_conf_changed = ("readiness" in changes) and ("qc_confidence" in changes["readiness"])
        qc_mode_changed = ("identifiers" in changes) and ("qc_mode" in changes["identifiers"])

        data_changed = ("measurement_ids_used" in changes) or ("gate_outcomes" in changes) or ("readiness" in changes) or ("evidence_by_metric" in changes)

        if policy_changed:
            drift = "policy_drift"
        elif structural_changed:
            drift = "structural_drift"
        elif qc_mode_changed or qc_conf_changed:
            drift = "qc_drift"
        elif data_changed:
            drift = "data_drift"
        else:
            drift = "structural_drift"

    summary = {
        "drift_label": drift,
        "policy_semantics_hash": {"id1": sem1, "id2": sem2},
        "policy_package_hash": {"id1": pkg1, "id2": pkg2},
        "catalog_hash": {"id1": cat_hash1, "id2": cat_hash2},
        "coverage_fingerprint": {"id1": cov_fp1, "id2": cov_fp2},
        "qc_mode": {"id1": qc_mode1, "id2": qc_mode2},
        "selection_semantics_version": {"id1": sel_sem1, "id2": sel_sem2},
        "integrity": {"id1": integrity1, "id2": integrity2},
        "engine": {
            "id1": {k: eng1.get(k) for k in ("engine_id", "schema_version", "selector_version", "evaluator_version")},
            "id2": {k: eng2.get(k) for k in ("engine_id", "schema_version", "selector_version", "evaluator_version")},
        },
    }

    return DriftResult(drift_label=drift, summary=summary, changes=changes)


def compute_snapshot_diff_by_id(*, db: Session, id1: int, id2: int) -> DriftResult:
    s1 = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(id1)).one_or_none()
    s2 = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(id2)).one_or_none()
    if s1 is None:
        raise ValueError(f"DecisionSnapshot not found: id={id1}")
    if s2 is None:
        raise ValueError(f"DecisionSnapshot not found: id={id2}")

    in1 = _as_dict(_json_load(s1.inputs_json))
    in2 = _as_dict(_json_load(s2.inputs_json))
    out1 = _as_dict(_json_load(s1.outputs_json))
    out2 = _as_dict(_json_load(s2.outputs_json))

    return compute_snapshot_diff_struct(out1=out1, in1=in1, out2=out2, in2=in2)
