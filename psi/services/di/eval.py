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


def _policy_required_gate_keys(policy_body: Dict[str, Any]) -> List[str]:
    """Policy-authoritative required gate keys in deterministic order.

    Authority order:
    1) `policy.shortlisting.required_gates` (preserve list order)
    2) infer from `policy.gates` insertion order, excluding conditional/optional gates
       (`if_present` gates and keys ending with `_optional`)
    """

    pol_short = (policy_body or {}).get("shortlisting") or {}
    if isinstance(pol_short, dict):
        req = pol_short.get("required_gates")
        if isinstance(req, list):
            out: List[str] = []
            seen: set[str] = set()
            for x in req:
                s = str(x).strip()
                if not s or s in seen:
                    continue
                seen.add(s)
                out.append(s)
            if out:
                return out

    gates = (policy_body or {}).get("gates") or {}
    if not isinstance(gates, dict):
        return []

    out: List[str] = []
    for gk, gd in gates.items():
        key = str(gk).strip()
        if not key:
            continue
        if not isinstance(gd, dict):
            gd = {}
        if isinstance(gd.get("if_present"), list):
            continue
        if key.lower().endswith("_optional"):
            continue
        out.append(key)
    return out


def _policy_required_metric_keys(policy_body: Dict[str, Any]) -> List[str]:
    """Policy-authoritative required metric keys in deterministic order."""

    gates = (policy_body or {}).get("gates") or {}
    if not isinstance(gates, dict):
        return []

    out: List[str] = []
    seen: set[str] = set()
    for gk in _policy_required_gate_keys(policy_body):
        gd = gates.get(gk) or {}
        if not isinstance(gd, dict):
            continue
        req: List[str] = []
        if isinstance(gd.get("require_all"), list):
            req = [str(x).strip() for x in gd.get("require_all") if str(x).strip()]
        elif isinstance(gd.get("require_any"), list):
            req = [str(x).strip() for x in gd.get("require_any") if str(x).strip()]
        for mk in req:
            if mk in seen:
                continue
            seen.add(mk)
            out.append(mk)
    return out


def _derive_reproducibility_signal(*, policy_body: Dict[str, Any], evidence_summary: list[Dict[str, Any]] | None) -> Dict[str, Any]:
    """Deterministic reproducibility signal from SoE evidence_summary counts.

    A required metric is reproducibility-positive when:
    - total_count > 1
    - usable_count > 1
    """

    required_metrics = sorted(set(_policy_required_metric_keys(policy_body)))
    summary_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(evidence_summary, list):
        for row in evidence_summary:
            if not isinstance(row, dict):
                continue
            mk = str(row.get("metric_key") or "").strip()
            if not mk or mk in summary_map:
                continue
            summary_map[mk] = row

    metrics: List[Dict[str, Any]] = []
    positive_count = 0
    for mk in required_metrics:
        row = summary_map.get(mk) or {}
        try:
            total_count = int(row.get("total_count") or 0)
        except Exception:
            total_count = 0
        try:
            usable_count = int(row.get("usable_count") or 0)
        except Exception:
            usable_count = 0
        is_positive = bool(total_count > 1 and usable_count > 1)
        if is_positive:
            positive_count += 1
        metrics.append(
            {
                "metric_key": mk,
                "total_count": int(total_count),
                "usable_count": int(usable_count),
                "reproducibility_positive": is_positive,
            }
        )

    required_count = len(required_metrics)
    if required_count == 0:
        status = "not_applicable"
    elif not summary_map:
        status = "not_available"
    else:
        status = "available"

    return {
        "status": status,
        "required_metric_count": int(required_count),
        "positive_required_metric_count": int(positive_count),
        "all_required_metrics_positive": bool(required_count > 0 and positive_count == required_count),
        "metrics": metrics,
    }


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


def _coerce_context_branch_require_any(x: Any) -> tuple[list[str], str]:
    if isinstance(x, list):
        vals = [str(v).strip() for v in x if str(v).strip()]
        return sorted(set(vals)), ""
    if isinstance(x, dict):
        req = x.get("require_any")
        vals = [str(v).strip() for v in req] if isinstance(req, list) else []
        vals = [v for v in vals if v]
        return sorted(set(vals)), str(x.get("explanation") or "").strip()
    return [], ""


def _resolve_gate_context_branch(*, gate_key: str, gate_def: Dict[str, Any], inputs_context: Dict[str, Any] | None) -> Dict[str, Any] | None:
    gd = gate_def if isinstance(gate_def, dict) else {}
    branch_map = gd.get("context_require_any_by_value")
    if not isinstance(branch_map, dict):
        return None

    ctx = inputs_context if isinstance(inputs_context, dict) else {}
    branch_keys = sorted([str(k).strip() for k in branch_map.keys() if str(k).strip()])
    selected_context_key = ""
    selected_context_value = ""
    selected_branch_key = ""
    selected_require_any: list[str] = []
    selected_expl = ""

    for ck in branch_keys:
        raw_map = branch_map.get(ck)
        if not isinstance(raw_map, dict):
            continue
        cval = str(ctx.get(ck) or "").strip()
        chosen = cval if cval in raw_map else ("_default" if "_default" in raw_map else "")
        if not chosen:
            continue
        req_any, expl = _coerce_context_branch_require_any(raw_map.get(chosen))
        selected_context_key = ck
        selected_context_value = cval
        selected_branch_key = chosen
        selected_require_any = req_any
        selected_expl = expl
        break

    if not selected_context_key:
        return None

    return {
        "gate_key": str(gate_key),
        "context_key": selected_context_key,
        "context_value": selected_context_value if selected_context_value else None,
        "selected_branch": selected_branch_key,
        "require_any": selected_require_any,
        "explanation": selected_expl or f"Selected {selected_context_key} branch {selected_branch_key}.",
    }


def derive_gate_outcomes(
    *,
    policy_body: Dict[str, Any],
    gate_results: list[Any],
    used_by_metric: Dict[str, Any],
    inputs_context: Dict[str, Any] | None = None,
    emit_context_branch_surface: bool = False,
) -> Dict[str, Any]:
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
        requirement_mode = "none"
        if isinstance(gd.get("require_all"), list):
            required_metrics = [str(x).strip() for x in gd.get("require_all") if str(x).strip()]
            requirement_mode = "require_all"
        elif isinstance(gd.get("require_any"), list):
            required_metrics = [str(x).strip() for x in gd.get("require_any") if str(x).strip()]
            requirement_mode = "require_any"
        required_metrics_base = sorted(set(required_metrics))
        context_branch = _resolve_gate_context_branch(gate_key=gk, gate_def=gd, inputs_context=inputs_context)
        if isinstance(context_branch, dict) and context_branch.get("require_any"):
            if requirement_mode == "require_any":
                required_metrics = list(context_branch.get("require_any") or [])
                context_branch["applied"] = True
            else:
                context_branch["applied"] = False
                context_branch["explanation"] = (
                    str(context_branch.get("explanation") or "").strip()
                    + " Branch map ignored because gate does not use require_any."
                ).strip()
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
        if emit_context_branch_surface:
            out[gk]["requirement_mode"] = requirement_mode
            out[gk]["required_metrics_base"] = required_metrics_base
            if isinstance(context_branch, dict):
                branch_out = dict(context_branch)
                branch_out["require_any"] = sorted([str(x) for x in (context_branch.get("require_any") or []) if str(x).strip()])
                out[gk]["context_branch"] = branch_out

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

    required_gate_keys = _policy_required_gate_keys(policy_body)
    required_gate_key_set = set(required_gate_keys)
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
        if str(gk) in required_gate_key_set:
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


def derive_shortlisting(
    *,
    policy_body: Dict[str, Any],
    decision_state: str,
    readiness: Dict[str, Any],
    gate_outcomes: Dict[str, Any],
    blockers: list[Dict[str, Any]],
    comparability: Dict[str, Any],
    metric_evaluations: Dict[str, Any],
    scope_type: str,
    scope_id: int,
    evidence_summary: list[Dict[str, Any]] | None = None,
    emit_v0_4_extensions: bool = False,
) -> Dict[str, Any] | None:
    """Deterministic shortlisting (single-scope baseline).

    Only enabled when policy explicitly allows it. Never overrides blockers/gates.
    """
    pol_short = (policy_body or {}).get("shortlisting") or {}
    if not isinstance(pol_short, dict):
        return None
    allow = bool(pol_short.get("allow_shortlisting") or pol_short.get("allow"))
    if not allow:
        return None

    min_cov = pol_short.get("min_required_coverage_ratio")
    try:
        min_cov_f = float(min_cov) if min_cov is not None else 1.0
    except Exception:
        min_cov_f = 1.0

    min_state = str(pol_short.get("min_readiness_state") or "ready").strip().lower()
    required_gates = _policy_required_gate_keys(policy_body)

    reasons: list[Dict[str, Any]] = []

    if blockers:
        reasons.append({"kind": "blockers_present", "count": int(len(blockers))})

    failing_gates = []
    for gk in [str(x) for x in required_gates]:
        status = str((gate_outcomes.get(gk) or {}).get("status") or "").strip().lower()
        if status and status != "pass":
            failing_gates.append(gk)
    if failing_gates:
        reasons.append({"kind": "hard_gates_not_passed", "gates": sorted(set(failing_gates))})

    state = str((readiness or {}).get("state") or "").strip().lower()
    if min_state and state != min_state:
        reasons.append({"kind": "readiness_state_below_threshold", "state": state, "required": min_state})

    cov = (readiness or {}).get("coverage") or {}
    try:
        cov_ratio = float(cov.get("coverage_ratio") or 0.0)
    except Exception:
        cov_ratio = 0.0
    if cov_ratio < min_cov_f:
        reasons.append({"kind": "coverage_below_threshold", "coverage_ratio": cov_ratio, "required": min_cov_f})
    if emit_v0_4_extensions:
        summary_map: Dict[str, Dict[str, Any]] = {}
        for row in (evidence_summary or []):
            if not isinstance(row, dict):
                continue
            mk = str(row.get("metric_key") or "").strip()
            if mk and mk not in summary_map:
                summary_map[mk] = row
        insufficient_counts: List[Dict[str, Any]] = []
        for mk in _policy_required_metric_keys(policy_body):
            row = summary_map.get(mk) or {}
            try:
                total_count = int(row.get("total_count") or 0)
            except Exception:
                total_count = 0
            try:
                usable_count = int(row.get("usable_count") or 0)
            except Exception:
                usable_count = 0
            if total_count <= 1 or usable_count <= 1:
                insufficient_counts.append(
                    {"metric_key": mk, "total_count": int(total_count), "usable_count": int(usable_count)}
                )
        if insufficient_counts:
            reasons.append(
                {
                    "kind": "insufficient_reproducibility_counts",
                    "metrics": insufficient_counts,
                    "rule": "total_count>1_and_usable_count>1",
                }
            )

    tie_break_hierarchy = [
        "readiness_completeness",
        "qc_coherence",
        "purity_aggregation",
        "reproducibility",
        "functional_potency",
    ]

    if reasons:
        out_refusal = {
            "enabled": True,
            "refused": True,
            "refusal_reason": "insufficient evidence to rank",
            "refusal_reasons": reasons,
            "tie_break_hierarchy": tie_break_hierarchy,
            "ranked_candidates": [],
        }
        if emit_v0_4_extensions:
            texts: List[str] = []
            for r in reasons:
                if not isinstance(r, dict):
                    texts.append(str(r))
                    continue
                kind = str(r.get("kind") or "")
                if kind == "insufficient_reproducibility_counts":
                    parts = []
                    for m in (r.get("metrics") or []):
                        if not isinstance(m, dict):
                            continue
                        parts.append(f"{m.get('metric_key')}:{int(m.get('total_count') or 0)}/{int(m.get('usable_count') or 0)}")
                    texts.append("insufficient_reproducibility_counts:" + ",".join(parts))
                elif kind == "hard_gates_not_passed":
                    gates = [str(x) for x in (r.get("gates") or []) if str(x).strip()]
                    texts.append("hard_gates_not_passed:" + ",".join(gates))
                elif kind == "coverage_below_threshold":
                    texts.append(
                        f"coverage_below_threshold:{float(r.get('coverage_ratio') or 0.0):.6f}<{float(r.get('required') or 0.0):.6f}"
                    )
                elif kind == "readiness_state_below_threshold":
                    texts.append(f"readiness_state:{r.get('state') or ''}!={r.get('required') or ''}")
                elif kind == "blockers_present":
                    texts.append(f"blockers_present:{int(r.get('count') or 0)}")
                else:
                    texts.append(kind or str(r))
            out_refusal["refusal_reasons_text"] = sorted(set(texts))
            out_refusal["tie_break"] = {"status": "refused", "hierarchy": tie_break_hierarchy}
            out_refusal["candidates"] = []
        return out_refusal

    def _eval_for(mk: str) -> Dict[str, Any]:
        ev = metric_evaluations.get(mk) if isinstance(metric_evaluations, dict) else None
        if not isinstance(ev, dict):
            return {"evaluated_status": "UNKNOWN", "interpretation_gap": False}
        return {
            "evaluated_status": str(ev.get("evaluated_status") or "UNKNOWN"),
            "interpretation_gap": bool(ev.get("interpretation_gap")),
        }

    comp = comparability or {}
    summ = (comp.get("summary") or {}) if isinstance(comp, dict) else {}
    qc_high = int(summ.get("high_severity_count") or 0)
    qc_total = int(summ.get("total_flags") or 0)

    purity = {
        "monomer_pct": _eval_for("monomer_pct"),
        "hmw_pct": _eval_for("hmw_pct"),
        "lmw_pct": _eval_for("lmw_pct"),
    }

    func_metrics = {
        "percent_killing": _eval_for("percent_killing"),
        "ec50": _eval_for("ec50"),
        "pass_fail": _eval_for("pass_fail"),
    }
    func_gap = any(v.get("interpretation_gap") for v in func_metrics.values())
    functional = {"context_valid": (not func_gap), "metrics": func_metrics}
    reproducibility = _derive_reproducibility_signal(policy_body=policy_body, evidence_summary=evidence_summary)

    candidate = {
        "candidate_id": f"{scope_type}:{int(scope_id)}",
        "scope_type": scope_type,
        "scope_id": int(scope_id),
        "decision_state": str(decision_state or ""),
        "readiness_completeness": cov_ratio,
        "qc_coherence": {"high_severity_count": qc_high, "total_flags": qc_total},
        "purity_aggregation": purity,
        "reproducibility": reproducibility,
        "functional_potency": functional,
        "tie_breaks": [
            {"key": "readiness_completeness", "value": cov_ratio},
            {"key": "qc_coherence", "value": {"high_severity_count": qc_high, "total_flags": qc_total}},
            {"key": "purity_aggregation", "value": purity},
            {"key": "reproducibility", "value": reproducibility},
            {"key": "functional_potency", "value": functional},
        ],
        "tie_break_explanations": [
            {
                "key": "readiness_completeness",
                "summary": "Coverage ratio used for readiness completeness.",
                "details": {"coverage_ratio": cov_ratio, "required": min_cov_f},
            },
            {
                "key": "qc_coherence",
                "summary": "QC coherence uses high-severity flags vs total flags.",
                "details": {"high_severity_count": qc_high, "total_flags": qc_total},
            },
            {
                "key": "purity_aggregation",
                "summary": "Purity aggregation derived from monomer/hmw/lmw value functions.",
                "details": purity,
            },
            {
                "key": "reproducibility",
                "summary": "Reproducibility uses SoE evidence_summary counts for required metrics (positive when total_count>1 and usable_count>1).",
                "details": reproducibility,
            },
            {
                "key": "functional_potency",
                "summary": "Functional potency considers context validity and metric evaluations.",
                "details": functional,
            },
        ],
    }

    out_ok = {
        "enabled": True,
        "refused": False,
        "refusal_reason": "",
        "refusal_reasons": [],
        "tie_break_hierarchy": tie_break_hierarchy,
        "ranked_candidates": [candidate],
    }
    if emit_v0_4_extensions:
        out_ok["refusal_reasons_text"] = []
        out_ok["tie_break"] = {"status": "evaluated", "hierarchy": tie_break_hierarchy}
        out_ok["candidates"] = [{"candidate_id": candidate.get("candidate_id")}]
    return out_ok
