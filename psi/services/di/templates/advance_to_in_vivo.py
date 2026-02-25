from __future__ import annotations

from typing import Any, Dict, List, Tuple

from psi.core.di.schema import EvidenceRef, GateResult
from psi.services.di.gates import evaluate_gates
from psi.services.di.sub_assessments import baseline_risk_flags_from_used, decision_state_from_gate_statuses


def _require_any(used: Dict[str, EvidenceRef], keys: List[str]) -> Tuple[bool, List[EvidenceRef]]:
    evs = [used[k] for k in keys if k in used]
    return (len(evs) > 0), evs


def _require_all(used: Dict[str, EvidenceRef], keys: List[str]) -> Tuple[bool, List[EvidenceRef], List[str]]:
    missing = [k for k in keys if k not in used]
    evs = [used[k] for k in keys if k in used]
    return (len(missing) == 0), evs, missing


def _metric_status(metric_evaluations: Dict[str, Any], metric_key: str) -> str:
    ev = metric_evaluations.get(metric_key) if isinstance(metric_evaluations, dict) else None
    if not isinstance(ev, dict):
        return ""
    return str(ev.get("evaluated_status") or "").strip().upper()


def _metric_ok(metric_evaluations: Dict[str, Any], metric_key: str) -> bool:
    status = _metric_status(metric_evaluations, metric_key)
    if not status:
        return True  # no value function defined
    return status in ("PASS", "WARN", "INFO")


def evaluate(
    *,
    used_by_metric: Dict[str, EvidenceRef],
    policy: Dict[str, Any],
    context: Dict[str, Any],
    metric_evaluations: Dict[str, Any] | None = None,
    enforce_value_functions: bool = False,
) -> Dict[str, Any]:
    gates_cfg = (policy or {}).get("gates") or {}
    gates: List[GateResult] = []
    blockers: List[Dict[str, Any]] = []
    risk_flags: List[Dict[str, Any]] = []
    metric_evaluations = metric_evaluations or {}
    use_thresholds = bool(enforce_value_functions)

    # Risk flags (v0.1) via shared deterministic helper.
    risk_flags.extend(baseline_risk_flags_from_used(used_by_metric=used_by_metric))

    gate_keys = [
        "G1_material_readiness",
        "G2_purity_integrity",
        "G3_endotoxin",
        "G4_functional",
        "G5_internalization_if_kd_present",
    ]
    gate_results = evaluate_gates(
        policy_body=policy,
        gate_keys=gate_keys,
        used_by_metric=used_by_metric,
        metric_evaluations=metric_evaluations,
        enforce_value_functions=use_thresholds,
        context=context,
    )

    for gr in gate_results:
        gk = str(gr.get("gate_key") or "")
        status = str(gr.get("status") or "")
        evs = gr.get("evidence_refs") or []
        missing = gr.get("missing") or []
        missing_any_of = gr.get("missing_any_of") or []
        failed = gr.get("failed_metrics") or []

        if gk == "G1_material_readiness":
            rationale = (
                "At least one material readiness metric present and within policy limits."
                if status == "pass" and use_thresholds
                else ("At least one material readiness metric present." if status == "pass" else "Missing or out-of-range material readiness metrics.")
            )
        elif gk == "G2_purity_integrity":
            rationale = (
                "Purity/integrity metrics present and within policy limits."
                if status == "pass" and use_thresholds
                else ("Purity/integrity metrics present." if status == "pass" else f"Missing or out-of-range: {', '.join(list(missing) + list(failed))}")
            )
        elif gk == "G3_endotoxin":
            rationale = (
                "Endotoxin value and limit present and within policy limits."
                if status == "pass" and use_thresholds
                else ("Endotoxin value and limit present." if status == "pass" else f"Missing or out-of-range: {', '.join(list(missing) + list(failed))}")
            )
        elif gk == "G4_functional":
            rationale = (
                "Functional evidence present and within policy limits."
                if status == "pass" and use_thresholds
                else ("Functional evidence present." if status == "pass" else "Missing or out-of-range functional evidence.")
            )
        elif gk == "G5_internalization_if_kd_present":
            rationale = (
                "Internalization/surface expression present when kd_nM present."
                if status == "pass"
                else "kd_nM present but internalization evidence missing."
            )
        else:
            rationale = "Gate evaluated from policy."

        gates.append(GateResult(
            gate_key=gk,
            status=status,
            rationale=rationale,
            evidence_refs=evs,
        ))

        if status != "pass":
            if failed:
                blockers.append({"blocker_key": "threshold_violation", "detail": {"gate": gk, "failed_metrics": failed}})
            if missing:
                blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": gk, "missing": missing}})
            elif missing_any_of:
                if gk == "G4_functional" and "conclusion" in used_by_metric:
                    blockers.append({"blocker_key": "insufficient_functional_anchor", "detail": {"present": ["conclusion"], "note": "Conclusion text alone is not a functional metric."}})
                blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": gk, "missing_any_of": missing_any_of}})
            if gk == "G5_internalization_if_kd_present":
                blockers.append({"blocker_key": "interpretation_gap_internalization", "detail": {"if_present": gates_cfg.get(gk, {}).get("if_present"), "missing_any_of": gates_cfg.get(gk, {}).get("require_any")}})
                risk_flags.append({"risk_flag": "internalization_sensitive_binding_gap"})
        if use_thresholds:
            for k in failed:
                risk_flags.append({"risk_flag": "threshold_violation", "detail": {"metric_key": k, "gate": gk, "status": _metric_status(metric_evaluations, k)}})

    # numeric expectation for endotoxin values
    for k in ("value_eu_ml", "limit_eu_ml"):
        if k in used_by_metric and used_by_metric[k].value_num is None:
            blockers.append({"blocker_key": "metric_present_but_non_numeric", "detail": {"metric_key": k, "measurement_id": used_by_metric[k].measurement_id}})

    # v0.1 default: require G1–G4 and G3
    required_gate_keys = {"G1_material_readiness", "G2_purity_integrity", "G3_endotoxin", "G4_functional"}
    decision_state, _ = decision_state_from_gate_statuses(
        gates=gates,
        required_gate_keys=sorted(list(required_gate_keys)),
        blockers=blockers,
    )

    return {"decision_state": decision_state, "gates": gates, "blockers": blockers, "risk_flags": risk_flags}
