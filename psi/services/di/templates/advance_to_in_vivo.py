from __future__ import annotations

from typing import Any, Dict, List, Tuple

from psi.core.di.schema import EvidenceRef, GateResult


def _require_any(used: Dict[str, EvidenceRef], keys: List[str]) -> Tuple[bool, List[EvidenceRef]]:
    evs = [used[k] for k in keys if k in used]
    return (len(evs) > 0), evs


def _require_all(used: Dict[str, EvidenceRef], keys: List[str]) -> Tuple[bool, List[EvidenceRef], List[str]]:
    missing = [k for k in keys if k not in used]
    evs = [used[k] for k in keys if k in used]
    return (len(missing) == 0), evs, missing


def evaluate(
    *,
    used_by_metric: Dict[str, EvidenceRef],
    policy: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    gates_cfg = (policy or {}).get("gates") or {}
    gates: List[GateResult] = []
    blockers: List[Dict[str, Any]] = []
    risk_flags: List[Dict[str, Any]] = []

    # Risk flags (v0.1)
    if any(ev.is_outlier for ev in used_by_metric.values()):
        risk_flags.append({"risk_flag": "outlier_present"})
    if any(ev.qc_status in ("unreviewed", "unknown") for ev in used_by_metric.values()):
        risk_flags.append({"risk_flag": "qc_uncertainty"})

    # ---- G1 Material readiness
    ok, evs = _require_any(used_by_metric, gates_cfg["G1_material_readiness"]["require_any"])
    gates.append(GateResult(
        gate_key="G1_material_readiness",
        status="pass" if ok else "fail",
        rationale="At least one material readiness metric present." if ok else "Missing both total_yield_mg and titer_mg_l.",
        evidence_refs=evs,
    ))
    if not ok:
        blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": "G1_material_readiness", "missing_any_of": gates_cfg["G1_material_readiness"]["require_any"]}})

    # ---- G2 Purity/Integrity
    ok, evs, missing = _require_all(used_by_metric, gates_cfg["G2_purity_integrity"]["require_all"])
    gates.append(GateResult(
        gate_key="G2_purity_integrity",
        status="pass" if ok else "fail",
        rationale="Purity/integrity metrics present." if ok else f"Missing: {', '.join(missing)}",
        evidence_refs=evs,
    ))
    if not ok:
        blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": "G2_purity_integrity", "missing": missing}})

    # ---- G3 Endotoxin
    ok, evs, missing = _require_all(used_by_metric, gates_cfg["G3_endotoxin"]["require_all"])
    gates.append(GateResult(
        gate_key="G3_endotoxin",
        status="pass" if ok else "fail",
        rationale="Endotoxin value and limit present." if ok else f"Missing: {', '.join(missing)}",
        evidence_refs=evs,
    ))
    if not ok:
        blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": "G3_endotoxin", "missing": missing}})

    # numeric expectation for endotoxin values
    for k in ("value_eu_ml", "limit_eu_ml"):
        if k in used_by_metric and used_by_metric[k].value_num is None:
            blockers.append({"blocker_key": "metric_present_but_non_numeric", "detail": {"metric_key": k, "measurement_id": used_by_metric[k].measurement_id}})

    # ---- G4 Functional evidence
    ok, evs = _require_any(used_by_metric, gates_cfg["G4_functional"]["require_any"])
    gates.append(GateResult(
        gate_key="G4_functional",
        status="pass" if ok else "fail",
        rationale="Functional evidence present." if ok else "Missing percent_killing, ec50, and pass_fail.",
        evidence_refs=evs,
    ))
    if not ok:
        if "conclusion" in used_by_metric:
            blockers.append({"blocker_key": "insufficient_functional_anchor", "detail": {"present": ["conclusion"], "note": "Conclusion text alone is not a functional metric."}})
        blockers.append({"blocker_key": "missing_required_metric", "detail": {"gate": "G4_functional", "missing_any_of": gates_cfg["G4_functional"]["require_any"]}})

    # ---- G5 conditional internalization if kd_nM present
    g5 = gates_cfg.get("G5_internalization_if_kd_present") or {}
    if bool(g5.get("enabled")) and any(k in used_by_metric for k in (g5.get("if_present") or [])):
        ok, evs = _require_any(used_by_metric, g5.get("require_any") or [])
        gates.append(GateResult(
            gate_key="G5_internalization_if_kd_present",
            status="pass" if ok else "fail",
            rationale="Internalization/surface expression present when kd_nM present." if ok else "kd_nM present but internalization evidence missing.",
            evidence_refs=evs,
        ))
        if not ok:
            blockers.append({"blocker_key": "interpretation_gap_internalization", "detail": {"if_present": g5.get("if_present"), "missing_any_of": g5.get("require_any")}})
            risk_flags.append({"risk_flag": "internalization_sensitive_binding_gap"})

    # v0.1 default: require G1–G4 and G3
    required_gate_keys = {"G1_material_readiness", "G2_purity_integrity", "G3_endotoxin", "G4_functional"}
    gate_map = {g.gate_key: g for g in gates}
    required_pass = all((k in gate_map and gate_map[k].status == "pass") for k in required_gate_keys)

    decision_state = "ready" if required_pass and not blockers else "not_ready"

    return {"decision_state": decision_state, "gates": gates, "blockers": blockers, "risk_flags": risk_flags}
