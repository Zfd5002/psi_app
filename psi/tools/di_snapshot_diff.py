"""DI DecisionSnapshot diff + drift diagnostics (analytical only).

Run:
  python -m psi.tools.di_snapshot_diff --id1 <snapshot_id> --id2 <snapshot_id>

Notes:
- Read-only: does not mutate the DB.
- Deterministic: output ordering is stable; no timestamps.
- Derived-only: drift labels are computed only from signals already embedded in snapshots.

This tool is intended for Roadmap v0.2 diff/diagnostics only.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from psi.core.models import DecisionSnapshot
from psi.services.decisions import stable_json_dumps


# -----------------------------
# DB helpers
# -----------------------------

def _default_db_path() -> str:
    # Mirrors psi.core.db.DB_PATH default: <psi package>/psi.sqlite
    psi_pkg_dir = Path(__file__).resolve().parents[2]
    return os.environ.get("PSI_DB_PATH", str(psi_pkg_dir / "psi.sqlite"))


def _open_session(db_path: str) -> Session:
    eng = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng, future=True)
    return SessionLocal()


def _load_snapshot(db: Session, snapshot_id: int) -> DecisionSnapshot:
    snap = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(snapshot_id)).one_or_none()
    if snap is None:
        raise ValueError(f"DecisionSnapshot not found: id={snapshot_id}")
    return snap


def _json_load(text: str) -> Any:
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


# -----------------------------
# Diff primitives (deterministic)
# -----------------------------


def _as_dict(x: Any) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}


def _as_list(x: Any) -> List[Any]:
    return x if isinstance(x, list) else []


def _canon(obj: Any) -> str:
    # Canonical string for deterministic set comparisons.
    return stable_json_dumps(obj)


def _sorted_unique(items: List[str]) -> List[str]:
    out = []
    seen = set()
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


def compute_snapshot_diff_struct(
    *,
    out1: Dict[str, Any],
    in1: Dict[str, Any],
    out2: Dict[str, Any],
    in2: Dict[str, Any],
) -> DriftResult:
    """Pure function: diff two parsed DI snapshot payloads.

    This is what smoke tests should call.
    """

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

    # --- structural diff sections ---
    changes: Dict[str, Any] = {}

    # readiness
    def _diff_simple(a: Any, b: Any) -> Optional[Dict[str, Any]]:
        if _canon(a) == _canon(b):
            return None
        return {"from": a, "to": b}

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
    # notes are lists; diff as sets
    notes1 = _sorted_unique([str(x) for x in (_as_list(qc1.get("notes")) or []) if str(x).strip()])
    notes2 = _sorted_unique([str(x) for x in (_as_list(qc2.get("notes")) or []) if str(x).strip()])
    if notes1 != notes2:
        qc_changes["notes"] = {"removed": [x for x in notes1 if x not in set(notes2)], "added": [x for x in notes2 if x not in set(notes1)]}
    if qc_changes:
        readiness_changes["qc_confidence"] = qc_changes

    # readiness.comparability
    comp1 = _as_dict(readiness1.get("comparability"))
    comp2 = _as_dict(readiness2.get("comparability"))
    comp_changes: Dict[str, Any] = {}
    mic1 = _sorted_unique([str(x) for x in (_as_list(comp1.get("method_incomparable_metrics")) or []) if str(x).strip()])
    mic2 = _sorted_unique([str(x) for x in (_as_list(comp2.get("method_incomparable_metrics")) or []) if str(x).strip()])
    if mic1 != mic2:
        comp_changes["method_incomparable_metrics"] = {"removed": [x for x in mic1 if x not in set(mic2)], "added": [x for x in mic2 if x not in set(mic1)]}
    n1 = _sorted_unique([str(x) for x in (_as_list(comp1.get("notes")) or []) if str(x).strip()])
    n2 = _sorted_unique([str(x) for x in (_as_list(comp2.get("notes")) or []) if str(x).strip()])
    if n1 != n2:
        comp_changes["notes"] = {"removed": [x for x in n1 if x not in set(n2)], "added": [x for x in n2 if x not in set(n1)]}
    if comp_changes:
        readiness_changes["comparability"] = comp_changes

    # readiness.blockers
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
        # both present
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

    # measurement ids used
    if mids1 != mids2:
        changes["measurement_ids_used"] = {
            "removed": [x for x in mids1 if x not in set(mids2)],
            "added": [x for x in mids2 if x not in set(mids1)],
        }

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
    # precedence is internal (not user-configurable):
    # policy_drift > structural_drift > qc_drift > data_drift > no_change

    if not changes:
        drift = "no_change"
    else:
        policy_changed = (sem1 != sem2) or (pkg1 != pkg2) or (cat_hash1 != cat_hash2)
        structural_changed = ("identifiers" in changes) and any(
            k in changes["identifiers"]
            for k in ("engine_id", "schema_version", "selector_version", "evaluator_version", "selection_semantics_version")
        )

        # QC drift: qc_mode changes OR qc_confidence changes while policy/structure unchanged
        qc_conf_changed = ("readiness" in changes) and ("qc_confidence" in changes["readiness"])
        qc_mode_changed = ("identifiers" in changes) and ("qc_mode" in changes["identifiers"])

        data_changed = ("measurement_ids_used" in changes) or ("gate_outcomes" in changes) or ("readiness" in changes)

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
        "engine": {
            "id1": {k: eng1.get(k) for k in ("engine_id", "schema_version", "selector_version", "evaluator_version")},
            "id2": {k: eng2.get(k) for k in ("engine_id", "schema_version", "selector_version", "evaluator_version")},
        },
    }

    return DriftResult(drift_label=drift, summary=summary, changes=changes)


def compute_snapshot_diff_by_id(*, db: Session, id1: int, id2: int) -> DriftResult:
    s1 = _load_snapshot(db, int(id1))
    s2 = _load_snapshot(db, int(id2))

    in1 = _as_dict(_json_load(s1.inputs_json))
    in2 = _as_dict(_json_load(s2.inputs_json))
    out1 = _as_dict(_json_load(s1.outputs_json))
    out2 = _as_dict(_json_load(s2.outputs_json))

    return compute_snapshot_diff_struct(out1=out1, in1=in1, out2=out2, in2=in2)


# -----------------------------
# Rendering
# -----------------------------


def _render_text(res: DriftResult, *, id1: int, id2: int) -> str:
    lines: List[str] = []
    lines.append("DI SNAPSHOT DIFF")
    lines.append(f"id1={id1}  id2={id2}")
    lines.append("")

    s = res.summary
    lines.append("SUMMARY")
    lines.append(f"- drift_label: {res.drift_label}")
    lines.append(f"- policy_semantics_hash: {s['policy_semantics_hash']['id1']} -> {s['policy_semantics_hash']['id2']}")
    lines.append(f"- policy_package_hash:   {s['policy_package_hash']['id1']} -> {s['policy_package_hash']['id2']}")
    lines.append(f"- catalog_hash:          {s['catalog_hash']['id1']} -> {s['catalog_hash']['id2']}")
    lines.append(f"- coverage_fingerprint:  {s['coverage_fingerprint']['id1']} -> {s['coverage_fingerprint']['id2']}")
    lines.append(f"- qc_mode:               {s['qc_mode']['id1']} -> {s['qc_mode']['id2']}")
    lines.append(f"- selection_semantics:   {s['selection_semantics_version']['id1']} -> {s['selection_semantics_version']['id2']}")
    lines.append("")

    if not res.changes:
        lines.append("DETAIL")
        lines.append("- no changes")
        return "\n".join(lines) + "\n"

    lines.append("DETAIL")

    def _emit_section(title: str) -> None:
        lines.append("")
        lines.append(title)

    # Deterministic section order
    for section in ("hashes", "identifiers", "readiness", "gate_outcomes", "measurement_ids_used"):
        if section not in res.changes:
            continue
        _emit_section(section)
        payload = res.changes[section]

        if section in ("hashes", "identifiers"):
            for k in sorted(payload.keys()):
                v = payload[k]
                if isinstance(v, dict) and "from" in v and "to" in v:
                    lines.append(f"- {k}: {v['from']} -> {v['to']}")
                else:
                    lines.append(f"- {k}: {stable_json_dumps(v)}")
            continue

        if section == "measurement_ids_used":
            rem = payload.get("removed") or []
            add = payload.get("added") or []
            lines.append(f"- removed: {stable_json_dumps(rem)}")
            lines.append(f"- added:   {stable_json_dumps(add)}")
            continue

        if section == "readiness":
            for k in sorted(payload.keys()):
                v = payload[k]
                if k == "blockers":
                    rem = v.get("removed") or []
                    add = v.get("added") or []
                    lines.append(f"- blockers_removed: {stable_json_dumps(rem)}")
                    lines.append(f"- blockers_added:   {stable_json_dumps(add)}")
                elif isinstance(v, dict) and "from" in v and "to" in v:
                    lines.append(f"- {k}: {v['from']} -> {v['to']}")
                else:
                    lines.append(f"- {k}: {stable_json_dumps(v)}")
            continue

        if section == "gate_outcomes":
            for gk in sorted(payload.keys()):
                gi = payload[gk]
                lines.append(f"- {gk}:")
                # deterministically ordered gate fields
                if isinstance(gi, dict) and ("added" in gi or "removed" in gi):
                    if "added" in gi:
                        lines.append(f"    + added: {stable_json_dumps(gi['added'])}")
                    if "removed" in gi:
                        lines.append(f"    - removed: {stable_json_dumps(gi['removed'])}")
                    continue
                for kk in sorted(gi.keys()):
                    vv = gi[kk]
                    if isinstance(vv, dict) and "from" in vv and "to" in vv:
                        lines.append(f"    ~ {kk}: {vv['from']} -> {vv['to']}")
                    elif isinstance(vv, dict) and ("removed" in vv or "added" in vv):
                        lines.append(f"    ~ {kk}: removed={stable_json_dumps(vv.get('removed') or [])} added={stable_json_dumps(vv.get('added') or [])}")
                    else:
                        lines.append(f"    ~ {kk}: {stable_json_dumps(vv)}")

    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="DI DecisionSnapshot diff (analytical, deterministic)")
    p.add_argument("--id1", required=True, type=int, help="DecisionSnapshot id (first)")
    p.add_argument("--id2", required=True, type=int, help="DecisionSnapshot id (second)")
    p.add_argument("--db", default=_default_db_path(), help="Path to PSI sqlite DB (default: PSI_DB_PATH or psi/psi.sqlite)")
    p.add_argument("--format", default="text", choices=("text", "json"), help="Output format")

    args = p.parse_args(argv)

    db = _open_session(args.db)
    try:
        res = compute_snapshot_diff_by_id(db=db, id1=int(args.id1), id2=int(args.id2))
    finally:
        db.close()

    if args.format == "json":
        payload = {
            "drift_label": res.drift_label,
            "summary": res.summary,
            "changes": res.changes,
        }
        print(stable_json_dumps(payload))
    else:
        print(_render_text(res, id1=int(args.id1), id2=int(args.id2)), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
