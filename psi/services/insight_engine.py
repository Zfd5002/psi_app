from __future__ import annotations

from typing import Any

from psi.services.metric_catalog import metric_catalog_entry


def _sorted_unique(values: list[str]) -> list[str]:
    return sorted({str(v).strip() for v in values if str(v).strip()})


def _snapshot_output(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    out = snapshot.get("output")
    if isinstance(out, dict):
        return out
    return snapshot


def _metric_gate_index(output: dict[str, Any]) -> dict[str, list[str]]:
    gate_outcomes = output.get("gate_outcomes") if isinstance(output.get("gate_outcomes"), dict) else {}
    out: dict[str, list[str]] = {}
    for gate_key in sorted(str(k) for k in gate_outcomes.keys()):
        row = gate_outcomes.get(gate_key)
        if not isinstance(row, dict):
            continue
        for mk in sorted(str(x) for x in (row.get("missing") or []) if str(x).strip()):
            out.setdefault(mk, []).append(gate_key)
        for mk in sorted(str(x) for x in (row.get("failed_metrics") or []) if str(x).strip()):
            out.setdefault(mk, []).append(gate_key)
    return {k: sorted(v) for k, v in sorted(out.items(), key=lambda x: x[0])}


def extract_policy_expectations(policy: dict[str, Any] | None) -> list[dict[str, Any]]:
    p = policy if isinstance(policy, dict) else {}
    body = p.get("policy_body") if isinstance(p.get("policy_body"), dict) else p
    gates = body.get("gates") if isinstance(body, dict) and isinstance(body.get("gates"), dict) else {}
    out: list[dict[str, Any]] = []
    for gate_key in sorted(str(k) for k in gates.keys()):
        gd = gates.get(gate_key)
        if not isinstance(gd, dict):
            continue
        thresholds = gd.get("thresholds") if isinstance(gd.get("thresholds"), dict) else {}
        for mk in sorted(str(k) for k in thresholds.keys()):
            tv = thresholds.get(mk)
            if not isinstance(tv, dict):
                continue
            ce = metric_catalog_entry(mk)
            label = str(ce.get("label") or mk)
            unit = str(ce.get("unit") or "").strip()
            text = ""
            if tv.get("min_value") is not None:
                text = f"{label} >= {tv.get('min_value')}{(' ' + unit) if unit else ''}"
            elif tv.get("max_value") is not None:
                text = f"{label} <= {tv.get('max_value')}{(' ' + unit) if unit else ''}"
            elif tv.get("cap_value") is not None:
                text = f"{label} <= {tv.get('cap_value')}{(' ' + unit) if unit else ''}"
            elif tv.get("value") is not None and tv.get("op"):
                text = f"{label} {tv.get('op')} {tv.get('value')}{(' ' + unit) if unit else ''}"
            if text:
                out.append({"gate_key": gate_key, "metric_key": mk, "expectation": text})
        for mk in sorted(str(x) for x in (gd.get("require_all") or []) if str(x).strip()):
            ce = metric_catalog_entry(mk)
            label = str(ce.get("label") or mk)
            out.append({"gate_key": gate_key, "metric_key": mk, "expectation": f"{label} required"})
        req_any = sorted(str(x) for x in (gd.get("require_any") or []) if str(x).strip())
        if req_any:
            labels = [str(metric_catalog_entry(x).get("label") or x) for x in req_any]
            out.append({"gate_key": gate_key, "metric_key": "|".join(req_any), "expectation": f"one of [{', '.join(labels)}] required"})
    return sorted(
        out,
        key=lambda x: (str(x.get("metric_key") or ""), str(x.get("gate_key") or ""), str(x.get("expectation") or "")),
    )


def _metric_priority(
    *,
    metric_key: str,
    missing_metrics: list[str],
    failing_metrics: list[str],
    expectations: list[dict[str, Any]],
    metric_to_gates: dict[str, list[str]],
) -> tuple[int, int, str]:
    mk = str(metric_key)
    blocking_rank = 0
    if mk in failing_metrics:
        blocking_rank = 2
    elif mk in missing_metrics:
        blocking_rank = 1
    exp_count = sum(1 for e in expectations if str(e.get("metric_key") or "") == mk)
    gate_count = len(metric_to_gates.get(mk, []))
    return (-blocking_rank, -(exp_count + gate_count), mk)


def _classify_evidence(
    *,
    output: dict[str, Any],
    missing_metrics: list[str],
    failing_metrics: list[str],
    expectations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metric_to_gates = _metric_gate_index(output)
    used = output.get("state_of_evidence", {}).get("used") if isinstance(output.get("state_of_evidence"), dict) else {}
    exp_by_metric: dict[str, str] = {}
    for e in expectations:
        if not isinstance(e, dict):
            continue
        mk = str(e.get("metric_key") or "").strip()
        ex = str(e.get("expectation") or "").strip()
        if mk and ex and mk not in exp_by_metric:
            exp_by_metric[mk] = ex
    used_keys = sorted(str(k) for k in (used.keys() if isinstance(used, dict) else []) if str(k).strip())
    candidate_keys = sorted(set(used_keys + list(missing_metrics) + list(failing_metrics)))
    ranked = sorted(
        candidate_keys,
        key=lambda mk: _metric_priority(
            metric_key=mk,
            missing_metrics=missing_metrics,
            failing_metrics=failing_metrics,
            expectations=expectations,
            metric_to_gates=metric_to_gates,
        ),
    )
    strongest_blocking: list[dict[str, Any]] = []
    strongest_supporting: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for mk in ranked:
        gates = metric_to_gates.get(mk, [])
        u = used.get(mk) if isinstance(used, dict) and isinstance(used.get(mk), dict) else {}
        observed_value = None
        if isinstance(u, dict):
            if u.get("value_num") is not None:
                observed_value = u.get("value_num")
            elif u.get("value_text"):
                observed_value = u.get("value_text")
        required_threshold = exp_by_metric.get(mk, "")
        batch_hint = ""
        if isinstance(u, dict):
            if u.get("batch_id") is not None:
                batch_hint = str(u.get("batch_id"))
            elif isinstance(u.get("evidence_refs"), list) and u.get("evidence_refs"):
                r0 = u.get("evidence_refs")[0]
                if isinstance(r0, dict) and r0.get("batch_id") is not None:
                    batch_hint = str(r0.get("batch_id"))
        if mk in failing_metrics:
            strongest_blocking.append(
                {
                    "metric_key": mk,
                    "classification": "failing",
                    "related_gates": gates,
                    "observed_value": observed_value,
                    "required_threshold": required_threshold,
                    "batch": batch_hint,
                }
            )
        elif mk in missing_metrics:
            missing.append(
                {
                    "metric_key": mk,
                    "classification": "missing",
                    "related_gates": gates,
                    "observed_value": observed_value,
                    "required_threshold": required_threshold,
                    "batch": batch_hint,
                }
            )
            strongest_blocking.append(
                {
                    "metric_key": mk,
                    "classification": "missing",
                    "related_gates": gates,
                    "observed_value": observed_value,
                    "required_threshold": required_threshold,
                    "batch": batch_hint,
                }
            )
        else:
            strongest_supporting.append(
                {
                    "metric_key": mk,
                    "classification": "supporting",
                    "related_gates": gates,
                    "observed_value": observed_value,
                    "required_threshold": required_threshold,
                    "batch": batch_hint,
                }
            )
    return strongest_supporting, strongest_blocking, missing


def generate_decision_summary(bundle: dict[str, Any]) -> str:
    b = bundle if isinstance(bundle, dict) else {}
    status = str(b.get("molecule_status") or "not_assessed")
    missing = [str(x.get("metric_key") or "") for x in (b.get("missing_evidence") or []) if isinstance(x, dict)]
    failing = [str(x.get("metric_key") or "") for x in (b.get("failing_evidence") or []) if isinstance(x, dict)]
    clauses = [f"Molecule status is {status.replace('_', ' ')}."]
    if failing:
        clauses.append(f"Blocked by failing evidence: {', '.join(sorted(set(failing)))}.")
    if missing:
        clauses.append(f"Missing required evidence: {', '.join(sorted(set(missing)))}.")
    if not failing and not missing:
        clauses.append("No immediate blocking or missing evidence signals were detected.")
    return " ".join(clauses)


def build_insight_bundle(
    snapshot: dict[str, Any] | None,
    *,
    molecule_context: dict[str, Any] | None = None,
    measurements: list[dict[str, Any]] | None = None,
    policy_expectations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    del molecule_context
    del measurements
    output = _snapshot_output(snapshot)
    expectations = (
        sorted([x for x in (policy_expectations or []) if isinstance(x, dict)], key=lambda x: (str(x.get("metric_key") or ""), str(x.get("expectation") or "")))
        if policy_expectations is not None
        else extract_policy_expectations(output.get("policy") if isinstance(output.get("policy"), dict) else {})
    )
    molecule_status = str(output.get("decision_state") or "not_assessed")
    gate_outcomes = output.get("gate_outcomes") if isinstance(output.get("gate_outcomes"), dict) else {}
    blockers = output.get("blockers") if isinstance(output.get("blockers"), list) else []

    missing_metrics: list[str] = []
    failing_metrics: list[str] = []
    blocking_issues: list[dict[str, Any]] = []

    for gate_key in sorted(str(k) for k in gate_outcomes.keys()):
        row = gate_outcomes.get(gate_key)
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        missing = sorted(str(x) for x in (row.get("missing") or []) if str(x).strip())
        failed = sorted(str(x) for x in (row.get("failed_metrics") or []) if str(x).strip())
        missing_metrics.extend(missing)
        failing_metrics.extend(failed)
        if status in {"fail", "hold"}:
            blocking_issues.append(
                {
                    "gate_key": gate_key,
                    "status": status,
                    "missing_metrics": missing,
                    "failing_metrics": failed,
                }
            )

    for b in blockers:
        if not isinstance(b, dict):
            continue
        bk = str(b.get("blocker_key") or "")
        if not bk:
            continue
        blocking_issues.append(
            {
                "gate_key": str((b.get("detail") or {}).get("gate") or ""),
                "status": "blocker",
                "blocker_key": bk,
                "missing_metrics": sorted(str(x) for x in ((b.get("detail") or {}).get("missing") or []) if str(x).strip()),
                "failing_metrics": sorted(str(x) for x in ((b.get("detail") or {}).get("failed_metrics") or []) if str(x).strip()),
            }
        )

    blocking_issues = sorted(
        blocking_issues,
        key=lambda x: (
            str(x.get("gate_key") or ""),
            str(x.get("status") or ""),
            str(x.get("blocker_key") or ""),
        ),
    )
    missing_metrics = _sorted_unique(missing_metrics)
    failing_metrics = _sorted_unique(failing_metrics)

    recommended_experiments = [
        {
            "priority": i + 1,
            "metric_key": mk,
            "reason": "missing_required_metric",
            "suggested_assay": f"Add measurement for {mk}",
        }
        for i, mk in enumerate(missing_metrics)
    ] + [
        {
            "priority": len(missing_metrics) + i + 1,
            "metric_key": mk,
            "reason": "failing_metric",
            "suggested_assay": f"Repeat/confirm {mk}",
        }
        for i, mk in enumerate(failing_metrics)
    ]

    metric_to_gates = _metric_gate_index(output)
    missing_evidence = [{"metric_key": mk, "related_gates": metric_to_gates.get(mk, [])} for mk in missing_metrics]
    failing_evidence = [{"metric_key": mk, "related_gates": metric_to_gates.get(mk, [])} for mk in failing_metrics]
    strongest_supporting, strongest_blocking, missing_ranked = _classify_evidence(
        output=output,
        missing_metrics=missing_metrics,
        failing_metrics=failing_metrics,
        expectations=expectations,
    )
    missing_evidence = [
        {
            "metric_key": str(x.get("metric_key") or ""),
            "related_gates": list(x.get("related_gates") or []),
            "observed_value": x.get("observed_value"),
            "required_threshold": str(x.get("required_threshold") or ""),
            "batch": str(x.get("batch") or ""),
            "classification": str(x.get("classification") or "missing"),
        }
        for x in missing_ranked
    ]

    out_bundle = {
        "molecule_status": molecule_status,
        "blocking_issues": blocking_issues,
        "missing_evidence": missing_evidence,
        "failing_evidence": failing_evidence,
        "recommended_experiments": recommended_experiments,
        "decision_summary": "",
        "strongest_supporting_evidence": strongest_supporting,
        "strongest_blocking_evidence": strongest_blocking,
    }
    out_bundle["decision_summary"] = generate_decision_summary(out_bundle)
    return out_bundle


def summarize_trend_signals(
    trends: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    t = trends if isinstance(trends, dict) else {}
    series = t.get("series") if isinstance(t.get("series"), dict) else {}
    out: list[dict[str, Any]] = []
    for mk in sorted(str(k) for k in series.keys()):
        pts = [p for p in (series.get(mk) or []) if isinstance(p, dict) and p.get("value") is not None]
        if len(pts) < 2:
            out.append({"metric_key": mk, "signal": "stable", "delta": 0.0})
            continue
        first = float(pts[0].get("value"))
        last = float(pts[-1].get("value"))
        delta = last - first
        signal = "stable"
        if delta > 0:
            signal = "improving"
        elif delta < 0:
            signal = "declining"
        out.append({"metric_key": mk, "signal": signal, "delta": round(delta, 6)})
    return out
