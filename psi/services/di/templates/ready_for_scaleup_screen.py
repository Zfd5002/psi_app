from __future__ import annotations

from typing import Any, Dict, List

from psi.core.di.schema import EvidenceRef, GateResult
from psi.services.di.gates import evaluate_gates
from psi.services.di.sub_assessments import baseline_risk_flags_from_used, decision_state_from_gate_statuses


def _gate_order(policy: Dict[str, Any]) -> list[str]:
    body = policy or {}
    order = body.get("gate_order") if isinstance(body.get("gate_order"), list) else []
    if order:
        return [str(k) for k in order if str(k).strip()]
    gates_cfg = body.get("gates") if isinstance(body.get("gates"), dict) else {}
    return sorted([str(k) for k in gates_cfg.keys()])


def _required_gate_keys(policy: Dict[str, Any], gate_keys: list[str]) -> list[str]:
    body = policy or {}
    req = body.get("required_gate_keys") if isinstance(body.get("required_gate_keys"), list) else []
    if req:
        return [str(k) for k in req if str(k).strip()]
    return list(gate_keys)


def evaluate(
    *,
    used_by_metric: Dict[str, EvidenceRef],
    policy: Dict[str, Any],
    context: Dict[str, Any],
    metric_evaluations: Dict[str, Any] | None = None,
    enforce_value_functions: bool = False,
) -> Dict[str, Any]:
    gate_keys = _gate_order(policy)
    required_gate_keys = _required_gate_keys(policy, gate_keys)
    metric_evaluations = metric_evaluations or {}

    gates: List[GateResult] = []
    blockers: List[Dict[str, Any]] = []
    risk_flags: List[Dict[str, Any]] = []

    # Risk flags (minimal, deterministic) via shared helper.
    risk_flags.extend(baseline_risk_flags_from_used(used_by_metric=used_by_metric))

    gate_results = evaluate_gates(
        policy_body=policy,
        gate_keys=gate_keys,
        used_by_metric=used_by_metric,
        metric_evaluations=metric_evaluations,
        enforce_value_functions=bool(enforce_value_functions),
        context=context,
    )

    for gr in gate_results:
        gk = str(gr.get("gate_key") or "")
        status = str(gr.get("status") or "")
        evs = gr.get("evidence_refs") or []
        missing = gr.get("missing") or []
        missing_any_of = gr.get("missing_any_of") or []
        failed = gr.get("failed_metrics") or []

        gates.append(
            GateResult(
                gate_key=gk,
                status=status,
                rationale="Gate evaluated from policy.",
                evidence_refs=evs,
            )
        )

        if status != "pass":
            if failed:
                blockers.append({"blocker_key": "threshold_violation", "detail": {"gate": gk, "failed_metrics": failed}})
                if enforce_value_functions:
                    for k in failed:
                        risk_flags.append({"risk_flag": "threshold_violation", "detail": {"metric_key": k, "gate": gk}})
            if missing:
                blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": gk, "missing": missing}})
            elif missing_any_of:
                blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": gk, "missing_any_of": missing_any_of}})

    decision_state, _ = decision_state_from_gate_statuses(
        gates=gates,
        required_gate_keys=required_gate_keys,
        blockers=blockers,
    )

    return {"decision_state": decision_state, "gates": gates, "blockers": blockers, "risk_flags": risk_flags}
