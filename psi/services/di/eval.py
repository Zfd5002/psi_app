"""DI evaluation + readiness derivations.

These helpers are derived-only reporting layers and must remain deterministic.
They MUST NOT change gate evaluation semantics.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _severity_rank(sev: str) -> int:
    s = str(sev or "").strip().lower()
    return {"high": 0, "moderate": 1, "low": 2}.get(s, 9)


def _stable_float_ratio(n: int, d: int, *, places: int = 6) -> float:
    if d <= 0:
        return 0.0
    try:
        return round(float(n) / float(d), int(places))
    except Exception:
        return 0.0


def _gate_results_by_key(gate_results: list[Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for g in gate_results or []:
        try:
            gk = str(getattr(g, "gate_key", "") or "").strip()
        except Exception:
            gk = ""
        if not gk:
            continue
        out[gk] = g
    return out


def derive_gate_outcomes(*, policy_body: Dict[str, Any], gate_results: list[Any], used_by_metric: Dict[str, Any]) -> Dict[str, Any]:
    gates = (policy_body or {}).get("gates") or {}
    if not isinstance(gates, dict):
        gates = {}

    gr = _gate_results_by_key(gate_results)
    used_keys = set(str(k) for k in (used_by_metric or {}).keys())

    out: Dict[str, Any] = {}
    for gk in sorted([str(k) for k in gates.keys()]):
        gd = gates.get(gk) or {}
        if not isinstance(gd, dict):
            gd = {}

        required_metrics: List[str] = []
        if isinstance(gd.get("require_all"), list):
            required_metrics = [str(x).strip() for x in gd.get("require_all") if str(x).strip()]
        elif isinstance(gd.get("require_any"), list):
            required_metrics = [str(x).strip() for x in gd.get("require_any") if str(x).strip()]
        required_metrics = sorted(set(required_metrics))

        present_metrics = sorted([m for m in required_metrics if m in used_keys])
        missing_metrics = sorted([m for m in required_metrics if m not in used_keys])

        g = gr.get(gk)
        status = "na"
        if g is not None:
            try:
                st = str(getattr(g, "status", "") or "").strip().lower()
            except Exception:
                st = ""
            if st in ("pass", "fail", "hold", "na"):
                status = st
            elif st:
                status = st

        qc_notes: List[str] = []
        if status == "na":
            qc_notes.append("gate not evaluated (conditional or context)")
        else:
            unrev = []
            for mk in present_metrics:
                ev = (used_by_metric or {}).get(mk)
                if ev is None:
                    continue
                qc = str(getattr(ev, "qc_status", "") or "").strip().lower()
                if qc in ("unreviewed", "unknown", ""):
                    unrev.append(mk)
            unrev = sorted(set(unrev))
            if unrev:
                qc_notes.append(f"required metrics present but unreviewed/unknown QC: {', '.join(unrev)}")

        out[gk] = {
            "status": status,
            "required_metrics": required_metrics,
            "present_metrics": present_metrics,
            "missing_metrics": missing_metrics,
            "qc_notes": sorted(qc_notes),
        }

    return out


def derive_readiness(
    *,
    decision_state: str,
    decision_key: str,
    policy_body: Dict[str, Any],
    gate_results: list[Any],
    templ_blockers: list[Dict[str, Any]],
    used_by_metric: Dict[str, Any],
    ignored: list[Any],
    warnings: list[Dict[str, Any]],
    qc_mode: str,
) -> Dict[str, Any]:
    """Derived-only readiness structure.

    This function MUST NOT affect gate evaluation results; it only normalizes and
    summarizes what the template already produced.
    """

    ds = str(decision_state or "").strip().lower()

    gates = (policy_body or {}).get("gates") or {}
    if not isinstance(gates, dict):
        gates = {}

    required_gate_keys = ["G1_material_readiness", "G2_purity_integrity", "G3_endotoxin", "G4_functional"]
    required_metrics_set: set[str] = set()
    optional_metrics_set: set[str] = set()
    for gk, gd in gates.items():
        if not isinstance(gd, dict):
            continue
        req: List[str] = []
        if isinstance(gd.get("require_all"), list):
            req = [str(x).strip() for x in gd.get("require_all") if str(x).strip()]
        elif isinstance(gd.get("require_any"), list):
            req = [str(x).strip() for x in gd.get("require_any") if str(x).strip()]
        if str(gk) in required_gate_keys:
            required_metrics_set.update(req)
        else:
            optional_metrics_set.update(req)

    required_metrics = sorted(set(str(x) for x in required_metrics_set if str(x).strip()))
    optional_metrics = sorted(set(str(x) for x in optional_metrics_set if str(x).strip()))

    used_keys = set(str(k) for k in (used_by_metric or {}).keys())
    required_present = sum(1 for m in required_metrics if m in used_keys)
    required_total = len(required_metrics)
    optional_present = sum(1 for m in optional_metrics if m in used_keys)
    optional_total = len(optional_metrics)

    coverage = {
        "required_present": int(required_present),
        "required_total": int(required_total),
        "optional_present": int(optional_present),
        "optional_total": int(optional_total),
        "coverage_ratio": _stable_float_ratio(required_present, required_total, places=6),
    }

    reviewed_required_present = 0
    unreviewed_required_present = 0
    for mk in required_metrics:
        if mk not in used_keys:
            continue
        ev = (used_by_metric or {}).get(mk)
        qc = str(getattr(ev, "qc_status", "") or "").strip().lower() if ev is not None else ""
        if qc == "approved":
            reviewed_required_present += 1
        else:
            unreviewed_required_present += 1

    qc_notes: List[str] = []
    for w in warnings or []:
        try:
            kind = str((w or {}).get("kind") or "").strip()
        except Exception:
            kind = ""
        if kind == "qc_uncertainty":
            qc_notes.append("qc_uncertainty present in selected evidence")
            break
    if qc_mode == "strict" and ds == "cannot_assess":
        qc_notes.append("strict QC prevented any acceptable evidence")
    qc_notes = sorted(set(qc_notes))

    qc_confidence = {
        "qc_mode": str(qc_mode),
        "reviewed_required_present": int(reviewed_required_present),
        "unreviewed_required_present": int(unreviewed_required_present),
        "notes": qc_notes,
    }

    method_incomp: List[str] = []
    for ig in ignored or []:
        try:
            rk = str(getattr(ig, "reason_key", "") or "").strip()
        except Exception:
            rk = ""
        if rk != "method_incomparable":
            continue
        try:
            mk = str(getattr(ig, "metric_key", "") or "").strip()
        except Exception:
            mk = ""
        if mk:
            method_incomp.append(mk)
    method_incomp = sorted(set(method_incomp))

    comparability = {
        "method_incomparable_metrics": method_incomp,
        "notes": [],
    }

    blockers: List[Dict[str, Any]] = []
    for b in templ_blockers or []:
        bk = str((b or {}).get("blocker_key") or "").strip()
        detail = (b or {}).get("detail")
        metrics: List[str] = []
        gates_list: List[str] = []
        expl = ""
        key = "other"
        sev = "moderate"

        if bk in ("missing_required_metric", "missing_required", "missing_requirements"):
            key = "missing_required"
            sev = "high"
        elif bk in ("unreviewed_qc_required_metric", "qc_unreviewed_strict"):
            key = "unreviewed_qc"
            sev = "high"
        elif bk in ("method_incomparable", "method_incomparable_required"):
            key = "method_incomparable"
            sev = "moderate"

        if isinstance(detail, dict):
            ms = detail.get("missing_metrics") or detail.get("metrics") or []
            if isinstance(ms, list):
                metrics = [str(x).strip() for x in ms if str(x).strip()]
            gs = detail.get("gates") or []
            if isinstance(gs, list):
                gates_list = [str(x).strip() for x in gs if str(x).strip()]
            note = detail.get("note") or detail.get("explanation")
            if note is not None:
                expl = str(note)

        metrics = sorted(set(metrics))
        gates_list = sorted(set(gates_list))
        if not expl:
            expl = bk if bk else "blocker"

        blockers.append({"key": key, "severity": sev, "metrics": metrics, "gates": gates_list, "explanation": expl})

    if method_incomp:
        already = any((x or {}).get("key") == "method_incomparable" for x in blockers)
        if not already:
            blockers.append(
                {
                    "key": "method_incomparable",
                    "severity": "moderate",
                    "metrics": method_incomp,
                    "gates": [],
                    "explanation": "Evidence exists but is method-incomparable under policy taxonomy.",
                }
            )

    blockers = sorted(
        blockers,
        key=lambda x: (
            _severity_rank(str((x or {}).get("severity"))),
            str((x or {}).get("key") or ""),
            ",".join((x or {}).get("metrics") or []),
            ",".join((x or {}).get("gates") or []),
        ),
    )

    if ds == "ready":
        state = "ready"
    elif ds == "cannot_assess":
        state = "insufficient_evidence"
    elif blockers:
        state = "blocked"
    else:
        state = "not_ready"

    # v1.2.9i: normalized readiness fields (additive; arrays must exist)
    readiness_level = {
        "ready": "ready",
        "insufficient_evidence": "insufficient_evidence",
        "blocked": "blocked",
        "not_ready": "not_ready",
    }.get(state, state)

    failing_gate_keys: List[str] = []
    for g in gate_results or []:
        try:
            gk = str(getattr(g, "gate_key", "") or "").strip()
            st = str(getattr(g, "status", "") or "").strip().lower()
        except Exception:
            gk, st = "", ""
        if gk and st == "fail":
            failing_gate_keys.append(gk)
    blocking_gates = sorted(set(failing_gate_keys + [x for b in blockers for x in (b.get("gates") or [])]))

    blocking_reasons = sorted(set([str((b or {}).get("explanation") or "").strip() for b in blockers if str((b or {}).get("explanation") or "").strip()]))

    return {
        "state": state,
        "blockers": blockers,
        "coverage": coverage,
        "qc_confidence": qc_confidence,
        "comparability": comparability,
        # normalized fields
        "decision_context": str(decision_key),
        "readiness_level": readiness_level,
        "blocking_gates": blocking_gates,
        "blocking_reasons": blocking_reasons,
        "assumptions": [],
        "required_next_steps": [],
    }
