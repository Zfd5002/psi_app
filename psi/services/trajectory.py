from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule, Program
from psi.services.insight_engine import build_insight_bundle


def _safe_json(raw: str | None) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def predict_metric_delta(metric_key: str, experiment_type: str) -> dict[str, Any]:
    mk = str(metric_key or "").strip()
    et = str(experiment_type or "").strip().lower()
    mapping: list[tuple[tuple[str, ...], list[str]]] = [
        (("kd", "bli", "spr", "binding"), ["kd_nM"]),
        (("sec", "hplc", "purity"), ["sec_monomer_pct", "hwm_pct"]),
        (("internalization", "cell uptake"), ["internalization_score"]),
        (("tm", "dsf", "stability"), ["tm_c"]),
    ]
    for keys, impacted in mapping:
        if any(k in et for k in keys):
            metrics = sorted({*(x for x in impacted if x), *( [mk] if mk else [])})
            return {
                "metric_key": mk,
                "experiment_type": et,
                "impacted_metrics": metrics,
                "assumed_direction": "improve",
            }
    return {
        "metric_key": mk,
        "experiment_type": et,
        "impacted_metrics": [mk] if mk else [],
        "assumed_direction": "improve",
    }


def _latest_snapshot_output(db: Session, *, molecule_id: int) -> tuple[int | None, dict[str, Any]]:
    snap = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .first()
    )
    if snap is None:
        return None, {}
    return int(snap.id), _safe_json(snap.outputs_json)


def _default_simulated_value(metric_key: str) -> float:
    mk = str(metric_key or "").strip().lower()
    defaults = {
        "kd_nm": 1.0,
        "sec_monomer_pct": 95.0,
        "hwm_pct": 1.0,
        "tm_c": 75.0,
        "internalization_score": 0.8,
    }
    return float(defaults.get(mk, 1.0))


def predict_gate_transitions(
    metric_changes: list[dict[str, Any]],
    *,
    gate_context: dict[str, list[str]] | None = None,
) -> list[dict[str, str]]:
    by_gate: dict[str, str] = {}
    gc = gate_context if isinstance(gate_context, dict) else {}
    for row in metric_changes:
        if not isinstance(row, dict):
            continue
        mk = str(row.get("metric_key") or "").strip()
        if not mk:
            continue
        for gk in sorted(str(x) for x in (gc.get(mk) or []) if str(x).strip()):
            by_gate[gk] = "improved"
    out = [
        {
            "gate_key": gk,
            "gate_before": "fail_or_hold",
            "gate_after": "pass",
            "delta": by_gate[gk],
        }
        for gk in sorted(by_gate.keys())
    ]
    return out


def predict_readiness_shift(
    gate_changes: list[dict[str, Any]],
    metric_changes: list[dict[str, Any]],
    *,
    readiness_before: str,
    required_gate_keys: list[str] | None = None,
    failing_gate_keys_before: list[str] | None = None,
) -> dict[str, str]:
    before = str(readiness_before or "not_assessed").strip().lower() or "not_assessed"
    changed_metrics = any(str(x.get("metric_key") or "").strip() for x in metric_changes if isinstance(x, dict))
    gate_rows = [x for x in gate_changes if isinstance(x, dict)]
    required = sorted({str(x).strip() for x in (required_gate_keys or []) if str(x).strip()})
    if not required:
        required = sorted({str(x.get("gate_key") or "").strip() for x in gate_rows if str(x.get("gate_key") or "").strip()})

    status_before: dict[str, str] = {}
    status_after: dict[str, str] = {}
    for gk in required:
        status_before[gk] = "fail_or_hold"
        status_after[gk] = "fail_or_hold"
    for row in gate_rows:
        gk = str(row.get("gate_key") or "").strip()
        if not gk:
            continue
        gb = str(row.get("gate_before") or "fail_or_hold").strip().lower() or "fail_or_hold"
        raw_after = str(row.get("gate_after") or "").strip().lower()
        if raw_after:
            ga = raw_after
        elif str(row.get("delta") or "").strip().lower() == "improved":
            ga = "pass"
        else:
            ga = gb
        status_before[gk] = gb
        status_after[gk] = ga

    failing_before_set = {str(x).strip() for x in (failing_gate_keys_before or []) if str(x).strip()}
    if failing_before_set:
        for gk in failing_before_set:
            status_before[gk] = "fail_or_hold"
            if gk not in status_after:
                status_after[gk] = "fail_or_hold"
        required = sorted(set(required) | failing_before_set)

    failing_before = sum(1 for gk in required if str(status_before.get(gk) or "").lower() != "pass")
    failing_after = sum(1 for gk in required if str(status_after.get(gk) or "").lower() != "pass")
    after = before
    if before == "ready":
        after = "ready"
    elif before != "not_assessed" and changed_metrics and failing_before > 0 and failing_after == 0:
        after = "ready"
    return {"readiness_before": before, "readiness_after": after}


def score_trajectory_confidence(
    *,
    metric_key: str,
    assumptions_count: int,
    historical_metric_stability: float,
) -> float:
    mk = str(metric_key or "").strip().lower()
    importance = 0.6
    if mk in {"kd_nm", "sec_monomer_pct", "tm_c", "internalization_score"}:
        importance = 0.85
    assumptions_penalty = min(0.4, max(0.0, float(assumptions_count) * 0.1))
    stability = min(1.0, max(0.0, float(historical_metric_stability)))
    score = (0.55 * importance) + (0.45 * stability) - assumptions_penalty
    return min(1.0, max(0.0, round(score, 4)))


def simulate_experiment_outcome(
    db: Session,
    *,
    molecule_id: int,
    metric_key: str,
    simulated_value: float | int | str,
) -> dict[str, Any]:
    mk = str(metric_key or "").strip()
    snap_id, output = _latest_snapshot_output(db, molecule_id=int(molecule_id))
    bundle = build_insight_bundle(output if output else None)
    before = str(bundle.get("molecule_status") or "not_assessed")

    missing_rows = [x for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)]
    failing_rows = [x for x in (bundle.get("failing_evidence") or []) if isinstance(x, dict)]

    missing_metrics = {str(x.get("metric_key") or "").strip() for x in missing_rows if str(x.get("metric_key") or "").strip()}
    failing_metrics = {str(x.get("metric_key") or "").strip() for x in failing_rows if str(x.get("metric_key") or "").strip()}
    blocking_metrics = sorted(missing_metrics | failing_metrics)

    related_gates = sorted(
        {
            str(g)
            for x in (missing_rows + failing_rows)
            if str(x.get("metric_key") or "").strip() == mk
            for g in (x.get("related_gates") or [])
            if str(g).strip()
        }
    )

    addressed_blocker = mk in set(blocking_metrics)
    unresolved_after = [x for x in blocking_metrics if x != mk]
    failing_gate_keys_before = sorted(
        {
            str(g)
            for x in (missing_rows + failing_rows)
            for g in (x.get("related_gates") or ([x.get("gate_key")] if x.get("gate_key") else []))
            if str(g).strip()
        }
    )
    gate_context = {mk: related_gates} if mk else {}
    metric_changes = [{"metric_key": mk, "simulated_value": simulated_value}]
    predicted_gate_changes = predict_gate_transitions(
        metric_changes,
        gate_context=gate_context,
    )
    readiness_shift = predict_readiness_shift(
        predicted_gate_changes,
        metric_changes,
        readiness_before=before if addressed_blocker and not unresolved_after else before,
        required_gate_keys=failing_gate_keys_before,
        failing_gate_keys_before=failing_gate_keys_before,
    )

    assumptions_count = 0 if addressed_blocker else 2
    stability = 0.7 if snap_id is not None else 0.5
    confidence_score = score_trajectory_confidence(
        metric_key=mk,
        assumptions_count=assumptions_count,
        historical_metric_stability=stability,
    )
    confidence = "low"
    if confidence_score >= 0.75:
        confidence = "high"
    elif confidence_score >= 0.5:
        confidence = "medium"

    explanation = (
        f"Simulated {mk}={simulated_value} against latest DI snapshot"
        if snap_id is not None
        else f"Simulated {mk}={simulated_value} without DI snapshot context"
    )

    metric_delta = predict_metric_delta(mk, mk)
    return {
        "molecule_id": int(molecule_id),
        "source_snapshot_id": snap_id,
        "predicted_gate_changes": predicted_gate_changes,
        "predicted_readiness_change": {
            "before": str(readiness_shift.get("readiness_before") or before),
            "after": str(readiness_shift.get("readiness_after") or before),
        },
        "impacted_metrics": list(metric_delta.get("impacted_metrics") or []),
        "confidence_score": float(confidence_score),
        "confidence_level": confidence,
        "explanation": explanation,
    }


def generate_trajectory_candidates(db: Session, *, molecule_id: int) -> list[dict[str, Any]]:
    _snap_id, output = _latest_snapshot_output(db, molecule_id=int(molecule_id))
    bundle = build_insight_bundle(output if output else None)
    recs = [x for x in (bundle.get("recommended_experiments") or []) if isinstance(x, dict)]
    missing = {str(x.get("metric_key") or "").strip() for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)}
    failing = {str(x.get("metric_key") or "").strip() for x in (bundle.get("failing_evidence") or []) if isinstance(x, dict)}
    blockers = missing | failing
    out: list[dict[str, Any]] = []
    for rec in sorted(
        recs,
        key=lambda x: (
            int(x.get("priority") or 9999),
            str(x.get("metric_key") or ""),
            str(x.get("suggested_assay") or ""),
        ),
    ):
        mk = str(rec.get("metric_key") or "").strip()
        if not mk:
            continue
        sim = simulate_experiment_outcome(
            db,
            molecule_id=int(molecule_id),
            metric_key=mk,
            simulated_value=_default_simulated_value(mk),
        )
        before = str((sim.get("predicted_readiness_change") or {}).get("before") or "")
        after = str((sim.get("predicted_readiness_change") or {}).get("after") or "")
        readiness_gain = 1 if before != "ready" and after == "ready" else 0
        impacted = [x for x in (sim.get("impacted_metrics") or []) if str(x).strip()]
        metric_coverage = len({str(x).strip() for x in impacted if str(x).strip()} & blockers)
        gate_impact = int(len(sim.get("predicted_gate_changes") or []))
        out.append(
            {
                "molecule_id": int(molecule_id),
                "metric_key": mk,
                "suggested_assay": str(rec.get("suggested_assay") or ""),
                "reason": str(rec.get("reason") or ""),
                "expected_readiness_gain": int(readiness_gain),
                "metric_coverage_improvement": int(metric_coverage),
                "gate_impact": int(gate_impact),
                "confidence_score": float(sim.get("confidence_score") or 0.0),
                "confidence_level": str(sim.get("confidence_level") or "low"),
                "simulation": sim,
            }
        )
    return out


def _effort_estimate(candidate: dict[str, Any]) -> int:
    assay = str(candidate.get("suggested_assay") or "").strip().lower()
    if any(k in assay for k in ("internalization", "in vivo", "animal")):
        return 3
    if any(k in assay for k in ("sec", "hplc", "dsf")):
        return 2
    return 1


def rank_trajectory_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(r) for r in candidates if isinstance(r, dict)]
    for r in rows:
        r["effort_estimate"] = int(_effort_estimate(r))
    rows.sort(
        key=lambda r: (
            -int(r.get("expected_readiness_gain") or 0),
            -float(r.get("confidence_score") or 0.0),
            int(r.get("effort_estimate") or 0),
            -int(r.get("metric_coverage_improvement") or 0),
            str(r.get("metric_key") or ""),
        )
    )
    return rows


def build_program_trajectory(db: Session, *, program_id: int, limit: int = 20) -> dict[str, Any]:
    mids = [
        int(x[0])
        for x in (
            db.query(Molecule.id)
            .filter(Molecule.program_id == int(program_id))
            .order_by(Molecule.id.asc())
            .all()
        )
    ]
    rows: list[dict[str, Any]] = []
    for mid in mids:
        ranked = rank_trajectory_candidates(generate_trajectory_candidates(db, molecule_id=int(mid)))
        for r in ranked:
            rows.append(
                {
                    **r,
                    "program_id": int(program_id),
                    "molecule_id": int(mid),
                }
            )
    rows.sort(
        key=lambda r: (
            -int(r.get("expected_readiness_gain") or 0),
            -float(r.get("confidence_score") or 0.0),
            int(r.get("effort_estimate") or 0),
            int(r.get("molecule_id") or 0),
            str(r.get("metric_key") or ""),
        )
    )
    return {
        "program_id": int(program_id),
        "experiments": rows[: max(1, int(limit))],
    }


def build_portfolio_trajectory(db: Session, *, limit: int = 30) -> dict[str, Any]:
    programs = db.query(Program).order_by(Program.id.asc()).all()
    rows: list[dict[str, Any]] = []
    for p in programs:
        prog = build_program_trajectory(db, program_id=int(p.id), limit=15)
        for r in (prog.get("experiments") or []):
            rows.append(
                {
                    **dict(r),
                    "program_id": int(p.id),
                    "program_name": str(p.name or ""),
                }
            )
    rows.sort(
        key=lambda r: (
            -int(r.get("expected_readiness_gain") or 0),
            -float(r.get("confidence_score") or 0.0),
            int(r.get("effort_estimate") or 0),
            int(r.get("program_id") or 0),
            int(r.get("molecule_id") or 0),
            str(r.get("metric_key") or ""),
        )
    )
    return {"experiments": rows[: max(1, int(limit))]}


def simulate_experiment_set(
    db: Session,
    *,
    molecule_id: int,
    experiments: list[dict[str, Any]],
) -> dict[str, Any]:
    sims: list[dict[str, Any]] = []
    current_before = None
    current_after = None
    impacted_metrics: set[str] = set()
    gate_keys: set[str] = set()
    for exp in experiments:
        if not isinstance(exp, dict):
            continue
        mk = str(exp.get("metric_key") or "").strip()
        if not mk:
            continue
        sim_val = exp.get("simulated_value")
        if sim_val is None:
            sim_val = _default_simulated_value(mk)
        sim = simulate_experiment_outcome(
            db,
            molecule_id=int(molecule_id),
            metric_key=mk,
            simulated_value=sim_val,
        )
        if current_before is None:
            current_before = str((sim.get("predicted_readiness_change") or {}).get("before") or "not_assessed")
        current_after = str((sim.get("predicted_readiness_change") or {}).get("after") or current_before or "not_assessed")
        if current_after == "ready":
            current_before = current_before or "not_assessed"
        for x in (sim.get("impacted_metrics") or []):
            s = str(x or "").strip()
            if s:
                impacted_metrics.add(s)
        for g in (sim.get("predicted_gate_changes") or []):
            gk = str((g or {}).get("gate_key") or "").strip()
            if gk:
                gate_keys.add(gk)
        sims.append({"metric_key": mk, "simulation": sim})
    return {
        "molecule_id": int(molecule_id),
        "experiment_count": int(len(sims)),
        "experiments": sims,
        "cumulative_readiness_change": {
            "before": current_before or "not_assessed",
            "after": current_after or current_before or "not_assessed",
        },
        "impacted_metrics": sorted(impacted_metrics),
        "impacted_gates": sorted(gate_keys),
    }


def build_trajectory_tree(
    db: Session,
    *,
    molecule_id: int,
    experiments: list[dict[str, Any]] | None = None,
    max_depth: int = 3,
    branch_limit: int = 4,
) -> dict[str, Any]:
    base_rows = experiments if experiments is not None else rank_trajectory_candidates(
        generate_trajectory_candidates(db, molecule_id=int(molecule_id))
    )
    ordered = [
        dict(r)
        for r in sorted(
            [x for x in (base_rows or []) if isinstance(x, dict)],
            key=lambda r: (
                -int(r.get("expected_readiness_gain") or 0),
                -float(r.get("confidence_score") or 0.0),
                int(r.get("effort_estimate") or _effort_estimate(r)),
                str(r.get("metric_key") or ""),
                str(r.get("suggested_assay") or ""),
            ),
        )[: max(1, int(branch_limit))]
    ]
    depth_limit = max(1, int(max_depth))
    nodes: list[dict[str, Any]] = [
        {
            "node_id": "root",
            "parent_id": None,
            "depth": 0,
            "metric_key": "",
            "suggested_assay": "",
            "readiness_after": None,
            "confidence_score": None,
        }
    ]

    # Depth 1: root branching for top candidate experiments.
    for i, row in enumerate(ordered):
        sim = simulate_experiment_set(
            db,
            molecule_id=int(molecule_id),
            experiments=[{"metric_key": str(row.get("metric_key") or ""), "simulated_value": _default_simulated_value(str(row.get("metric_key") or ""))}],
        )
        nodes.append(
            {
                "node_id": f"n1_{i}",
                "parent_id": "root",
                "depth": 1,
                "metric_key": str(row.get("metric_key") or ""),
                "suggested_assay": str(row.get("suggested_assay") or ""),
                "readiness_after": str((sim.get("cumulative_readiness_change") or {}).get("after") or "not_assessed"),
                "confidence_score": float(row.get("confidence_score") or 0.0),
            }
        )

    # Deeper branching: deterministic pairwise continuations.
    if depth_limit >= 2:
        for i, row_a in enumerate(ordered):
            parent = f"n1_{i}"
            for j, row_b in enumerate(ordered):
                if j == i:
                    continue
                if j >= int(branch_limit):
                    break
                sim = simulate_experiment_set(
                    db,
                    molecule_id=int(molecule_id),
                    experiments=[
                        {"metric_key": str(row_a.get("metric_key") or ""), "simulated_value": _default_simulated_value(str(row_a.get("metric_key") or ""))},
                        {"metric_key": str(row_b.get("metric_key") or ""), "simulated_value": _default_simulated_value(str(row_b.get("metric_key") or ""))},
                    ],
                )
                nodes.append(
                    {
                        "node_id": f"n2_{i}_{j}",
                        "parent_id": parent,
                        "depth": 2,
                        "metric_key": str(row_b.get("metric_key") or ""),
                        "suggested_assay": str(row_b.get("suggested_assay") or ""),
                        "readiness_after": str((sim.get("cumulative_readiness_change") or {}).get("after") or "not_assessed"),
                        "confidence_score": float(row_b.get("confidence_score") or 0.0),
                    }
                )

    nodes = sorted(
        nodes,
        key=lambda n: (
            int(n.get("depth") or 0),
            str(n.get("parent_id") or ""),
            str(n.get("node_id") or ""),
        ),
    )
    return {
        "molecule_id": int(molecule_id),
        "nodes": nodes,
    }
