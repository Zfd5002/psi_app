from __future__ import annotations

"""Shared DI compute path used by both runner and anchored replay.

v1.2.9n governance hardening:
- Runner and anchored replay must use the same output assembly logic.
- This module defines a single pure function that computes the DI output
  from a provided `used_by_metric` map.

Hard constraints:
- No DB writes
- Deterministic ordering
- No wall-clock time
"""

import hashlib
import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from psi.core.di.schema import DIInput, EvidenceRef, IgnoredEvidence
from psi.services.di.templates.registry import resolve_template_entry, template_dependency_graph
from psi.services.di.eval import derive_gate_outcomes, derive_readiness, derive_shortlisting
from psi.services.di.comparability import compute_comparability, compute_comparability_for_batches
from psi.services.di.enrich import (
    build_soe_v0_2,
    build_soe_v0_3,
    coverage_fingerprint_payload,
    derive_metric_evaluations,
    derive_risk_flags_enriched,
    derive_suggestions,
)
from psi.services.di.nbe import build_experiment_suggestions
from psi.services.di.integrity import (
    compute_decision_output_hash,
    compute_decision_output_hash_v2,
    compute_evidence_fingerprint,
    compute_snapshot_content_hash,
)
from psi.services.di.util import parse_iso, stable_json_dumps, value_functions_enforcement_reason
from psi.services.di.soe import build_soe_v0_2_molecule, build_soe_v0_3_molecule
from psi.version import PSI_VERSION


def _to_dict(x: Any) -> Dict[str, Any]:
    """Best-effort conversion to a plain dict for JSON payloads.

    Accept both:
    - dataclass / pydantic-like objects with __dict__
    - already-materialized dicts (e.g., anchored replay using snapshot-stored metadata)
    """

    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    d = getattr(x, "__dict__", None)
    if isinstance(d, dict):
        return d
    return {"value": str(x)}


RANKING_RULE_VERSION = "v0.5.1"


def _ranking_factor(key: str, direction: str, value: Any, weight: float) -> Dict[str, Any]:
    return {"key": key, "direction": direction, "value": value, "weight": weight}


def _ranking_enabled(policy_body: Dict[str, Any]) -> bool:
    pol_short = (policy_body or {}).get("shortlisting") or {}
    if not isinstance(pol_short, dict):
        return False
    return bool(pol_short.get("allow_shortlisting") or pol_short.get("allow"))


def _policy_supports_context_branch_surface(pol: Any) -> bool:
    try:
        v = str(getattr(pol, "version", "") or "").strip().lower()
    except Exception:
        v = ""
    return v.startswith("v0.4")


def _should_emit_value_functions_enforced(inputs_obj: Dict[str, Any]) -> bool:
    flags = inputs_obj.get("output_extensions") if isinstance(inputs_obj, dict) else []
    if not isinstance(flags, list):
        return False
    return "value_functions_enforced_v0_1" in [str(x) for x in flags]


def _value_functions_enforcement_reason_for_compute(
    *,
    template_flag_enabled: bool,
    evaluator_version_expected: str,
    evaluator_version_actual: str,
) -> str:
    return value_functions_enforcement_reason(
        applicable=True,
        policy_flag_enabled=bool(template_flag_enabled),
        evaluator_version_expected=evaluator_version_expected,
        evaluator_version_actual=evaluator_version_actual,
    )


def _build_scope_semantics(
    *,
    di_in: DIInput,
    shortlisting: Dict[str, Any] | None,
    selection_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """Build v0.4+ explicit scope semantics (batch-first) without introducing scores."""

    scope_type = str(di_in.scope_type or "")
    refused = bool((shortlisting or {}).get("refused")) if isinstance(shortlisting, dict) else False
    batch_ranked_candidates: List[Dict[str, Any]] = []

    if not refused:
        if scope_type == "batch":
            batch_ranked_candidates = [{"batch_id": int(di_in.scope_id), "rank_source": "scope_batch"}]
        elif scope_type == "molecule":
            ordered = selection_provenance.get("batch_ids_ordered") or selection_provenance.get("batch_ids_all") or []
            seen: set[int] = set()
            for x in ordered:
                try:
                    bid = int(x)
                except Exception:
                    continue
                if bid in seen:
                    continue
                seen.add(bid)
                batch_ranked_candidates.append({"batch_id": bid, "rank_source": "selection_provenance_batch_order"})

    molecule_derived_candidates: List[Dict[str, Any]] = []
    if not refused:
        if scope_type == "molecule":
            mol_id = selection_provenance.get("molecule_id")
            try:
                mol_id_i = int(mol_id) if mol_id is not None else None
            except Exception:
                mol_id_i = None
            if mol_id_i is not None and batch_ranked_candidates:
                molecule_derived_candidates.append(
                    {
                        "molecule_id": mol_id_i,
                        "best_batch_id": int(batch_ranked_candidates[0]["batch_id"]),
                        "derivation_rule": "best_ready_batch_per_molecule",
                    }
                )
        elif scope_type == "batch":
            mol_id = selection_provenance.get("molecule_id")
            try:
                mol_id_i = int(mol_id) if mol_id is not None else None
            except Exception:
                mol_id_i = None
            if mol_id_i is not None:
                molecule_derived_candidates.append(
                    {
                        "molecule_id": mol_id_i,
                        "best_batch_id": int(di_in.scope_id),
                        "derivation_rule": "best_ready_batch_per_molecule",
                    }
                )

    notes = [
        "batch-first scope semantics (deterministic; no weighted scoring)",
        "molecule derivation uses best_ready_batch_per_molecule and never fabricates rankings when shortlisting is refused",
    ]
    if scope_type == "molecule":
        notes.append("batch ranking uses selection_provenance batch order as deterministic tie-break baseline for aggregated molecule scope")

    return {
        "ranked_entity": "batch",
        "scope_type": scope_type,
        "scope_id": int(di_in.scope_id),
        "molecule_derivation": "best_ready_batch_per_molecule",
        "refused": bool(refused),
        "batch_ranked_candidates": batch_ranked_candidates,
        "molecule_derived_candidates": molecule_derived_candidates,
        "notes": notes,
    }


def _score_from_factors(factors: List[Dict[str, Any]]) -> float:
    score = 0.0
    for f in factors:
        try:
            v = float(f.get("value") or 0.0)
            w = float(f.get("weight") or 0.0)
        except Exception:
            continue
        direction = str(f.get("direction") or "pro").strip().lower()
        if direction == "con":
            score -= v * w
        else:
            score += v * w
    return float(score)


def _ranking_sort_key(cand: Dict[str, Any]) -> tuple:
    score = float(cand.get("score") or 0.0)
    tb = cand.get("tie_breaker") if isinstance(cand.get("tie_breaker"), dict) else {}
    created_raw = tb.get("created_at")
    dt = parse_iso(str(created_raw)) if created_raw else None
    created_ts = dt.timestamp() if dt is not None else -1.0
    cid = int(cand.get("candidate_id") or 0)
    return (-score, -created_ts, -cid)


def _build_ranking(
    *,
    di_in: DIInput,
    out: Dict[str, Any],
    selection_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    scope_type = str(di_in.scope_type or "batch")
    candidates: List[Dict[str, Any]] = []

    if scope_type == "batch":
        factors: List[Dict[str, Any]] = []
        decision_state = str(out.get("decision_state") or "")
        if decision_state == "ready":
            factors.append(_ranking_factor("decision_state", "pro", 1.0, 50.0))
        elif decision_state == "not_ready":
            factors.append(_ranking_factor("decision_state", "con", 1.0, 50.0))
        else:
            factors.append(_ranking_factor("decision_state", "con", 1.0, 50.0))

        blockers = out.get("blockers") if isinstance(out.get("blockers"), list) else []
        factors.append(_ranking_factor("blockers_count", "con", float(len(blockers)), 5.0))

        comp = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
        summary = comp.get("summary") if isinstance(comp.get("summary"), dict) else {}
        high_sev = float(summary.get("high_severity_count") or 0)
        factors.append(_ranking_factor("comparability_high_severity", "con", high_sev, 3.0))

        soe = out.get("state_of_evidence") if isinstance(out.get("state_of_evidence"), dict) else {}
        soe_v0_2 = soe.get("soe_v0_2") if isinstance(soe.get("soe_v0_2"), dict) else {}
        coverage = soe_v0_2.get("coverage") if isinstance(soe_v0_2.get("coverage"), dict) else {}
        missing = float(len(coverage.get("metrics_missing") or []))
        present = float(len(coverage.get("metrics_present") or []))
        factors.append(_ranking_factor("metrics_present", "pro", present, 1.0))
        factors.append(_ranking_factor("metrics_missing", "con", missing, 1.0))

        warnings = soe.get("warnings") if isinstance(soe.get("warnings"), list) else []
        factors.append(_ranking_factor("warnings_count", "con", float(len(warnings)), 1.0))

        score = _score_from_factors(factors)
        cand = {
            "candidate_type": "batch",
            "candidate_id": int(di_in.scope_id),
            "score": score,
            "tie_breaker": {"created_at": None, "id": int(di_in.scope_id)},
            "factors": factors,
        }
        candidates.append(cand)
    else:
        batch_ids = selection_provenance.get("batch_ids_ordered") or selection_provenance.get("batch_ids_all") or []
        batch_ids = [int(x) for x in batch_ids if str(x).isdigit()]
        created_map = selection_provenance.get("batch_created_at") if isinstance(selection_provenance.get("batch_created_at"), dict) else {}
        metric_src = selection_provenance.get("metric_source_batch_ids") if isinstance(selection_provenance.get("metric_source_batch_ids"), dict) else {}
        batch_summaries = selection_provenance.get("batch_summaries") if isinstance(selection_provenance.get("batch_summaries"), list) else []
        summary_map: Dict[int, Dict[str, Any]] = {int(s.get("batch_id")): s for s in batch_summaries if isinstance(s, dict) and str(s.get("batch_id") or "").isdigit()}

        metrics_by_batch: Dict[int, int] = {}
        for mk, bid in metric_src.items():
            try:
                bid_i = int(bid)
            except Exception:
                continue
            metrics_by_batch[bid_i] = metrics_by_batch.get(bid_i, 0) + 1

        for bid in batch_ids:
            factors: List[Dict[str, Any]] = []
            mcount = float(metrics_by_batch.get(int(bid), 0))
            factors.append(_ranking_factor("metrics_sourced_count", "pro", mcount, 2.0))

            summ = summary_map.get(int(bid)) or {}
            used_cnt = float(summ.get("used_metric_count") or 0)
            ignored_cnt = float(summ.get("ignored_count") or 0)
            warn_cnt = float(summ.get("warning_count") or 0)

            factors.append(_ranking_factor("used_metric_count", "pro", used_cnt, 1.0))
            factors.append(_ranking_factor("ignored_count", "con", ignored_cnt, 0.5))
            factors.append(_ranking_factor("warning_count", "con", warn_cnt, 1.0))

            score = _score_from_factors(factors)
            cand = {
                "candidate_type": "batch",
                "candidate_id": int(bid),
                "score": score,
                "tie_breaker": {"created_at": created_map.get(str(bid)), "id": int(bid)},
                "factors": factors,
            }
            candidates.append(cand)

    candidates = sorted(candidates, key=_ranking_sort_key)
    winner_id = candidates[0]["candidate_id"] if candidates else None
    return {
        "scope_type": scope_type,
        "candidates": candidates,
        "winner_candidate_id": winner_id,
        "ranking_rule_version": RANKING_RULE_VERSION,
    }




def _normalize_ignored(ignored: List[Any]) -> List[IgnoredEvidence]:
    """Normalize ignored evidence entries to IgnoredEvidence objects.

    Runner selection produces IgnoredEvidence objects.
    Anchored replay may supply snapshot-stored dicts.

    Normalizing here prevents subtle drift in SoE packs and downstream logic.
    """
    out: List[IgnoredEvidence] = []
    for ig in ignored or []:
        if isinstance(ig, IgnoredEvidence):
            out.append(ig)
            continue
        if isinstance(ig, dict):
            try:
                payload = dict(ig)
                if "qc_source" not in payload and "qc_status" in payload:
                    payload["qc_source"] = payload.get("qc_status")
                out.append(IgnoredEvidence(**payload))
                continue
            except Exception:
                # Fall back to minimal safe representation; keep determinism.
                qc_source = None
                if ig.get("qc_source") is not None:
                    qc_source = str(ig.get("qc_source"))
                elif ig.get("qc_status") is not None:
                    qc_source = str(ig.get("qc_status"))
                out.append(IgnoredEvidence(
                    measurement_id=int(ig.get("measurement_id") or 0),
                    data_record_id=int(ig.get("data_record_id") or 0),
                    metric_key=str(ig.get("metric_key") or ""),
                    reason_key=str(ig.get("reason_key") or ""),
                    reason_detail=(str(ig.get("reason_detail")) if ig.get("reason_detail") is not None else None),
                    qc_source=qc_source,
                ))
                continue
        # Unknown type: stringify deterministically into reason_detail
        out.append(IgnoredEvidence(
            measurement_id=0,
            data_record_id=0,
            metric_key="",
            reason_key="unknown",
            reason_detail=str(ig),
            qc_source=None,
        ))
    return out


def _why_pointer_list_for_metric_ref(*, metric_key: str, ev: Any) -> List[Dict[str, Any]]:
    if ev is None:
        return []
    out: List[Dict[str, Any]] = []
    try:
        mid = getattr(ev, "measurement_id", None)
    except Exception:
        mid = None
    try:
        drid = getattr(ev, "data_record_id", None)
    except Exception:
        drid = None
    try:
        mks = str(getattr(ev, "metric_key_source", "") or "").strip()
    except Exception:
        mks = ""

    if mid is not None:
        out.append({"kind": "measurement", "id": int(mid), "metric_key": str(metric_key)})
        out.append({"kind": "measurement_field", "id": int(mid), "field": "qc_status", "metric_key": str(metric_key)})
        if mks:
            out.append({"kind": "measurement_field", "id": int(mid), "field": "metric_key_source", "metric_key": str(metric_key)})
    if drid is not None:
        out.append({"kind": "data_record", "id": int(drid), "metric_key": str(metric_key)})
    return sorted(
        out,
        key=lambda x: (
            str(x.get("kind") or ""),
            int(x.get("id") or 0),
            str(x.get("field") or ""),
            str(x.get("metric_key") or ""),
        ),
    )


def _why_gate_evidence_map(*, gate_outcomes: Dict[str, Any], used_by_metric: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for gk in sorted([str(k) for k in (gate_outcomes or {}).keys()]):
        gd = gate_outcomes.get(gk) if isinstance(gate_outcomes, dict) else None
        if not isinstance(gd, dict):
            out[gk] = []
            continue
        metric_keys = sorted(set([str(m) for m in (gd.get("present_metrics") or []) if str(m).strip()]))
        ptrs: List[Dict[str, Any]] = []
        for mk in metric_keys:
            ptrs.extend(_why_pointer_list_for_metric_ref(metric_key=mk, ev=(used_by_metric or {}).get(mk)))
        out[gk] = sorted(
            ptrs,
            key=lambda x: (
                str(x.get("kind") or ""),
                int(x.get("id") or 0),
                str(x.get("field") or ""),
                str(x.get("metric_key") or ""),
            ),
        )
    return out


def _build_why_evidence(
    *,
    out: Dict[str, Any],
    used_by_metric: Dict[str, Any],
    selection_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    shortlisting = out.get("shortlisting") if isinstance(out.get("shortlisting"), dict) else None
    ranking = out.get("ranking") if isinstance(out.get("ranking"), dict) else None

    gate_evidence = _why_gate_evidence_map(gate_outcomes=gate_outcomes, used_by_metric=used_by_metric)

    readiness_blocking_gates = [str(x) for x in (readiness.get("blocking_gates") or []) if str(x).strip()]
    readiness_evidence = {
        "blocking_gates": {
            gk: list(gate_evidence.get(gk) or []) for gk in sorted(set(readiness_blocking_gates))
        }
    }

    shortlisting_evidence: Dict[str, Any] = {
        "hard_gates": {},
        "ranked_candidates": [],
    }
    if isinstance(shortlisting, dict):
        refusal_reasons = shortlisting.get("refusal_reasons") if isinstance(shortlisting.get("refusal_reasons"), list) else []
        hard_gate_keys: List[str] = []
        for rr in refusal_reasons:
            if not isinstance(rr, dict):
                continue
            if str(rr.get("kind") or "") != "hard_gates_not_passed":
                continue
            hard_gate_keys.extend([str(x) for x in (rr.get("gates") or []) if str(x).strip()])
        shortlisting_evidence["hard_gates"] = {
            gk: list(gate_evidence.get(gk) or []) for gk in sorted(set(hard_gate_keys))
        }

        for cand in (shortlisting.get("ranked_candidates") or []):
            if not isinstance(cand, dict):
                continue
            candidate_id = str(cand.get("candidate_id") or "")
            metric_keys: List[str] = []
            purity = cand.get("purity_aggregation") if isinstance(cand.get("purity_aggregation"), dict) else {}
            metric_keys.extend(sorted([str(k) for k in purity.keys() if str(k).strip()]))
            func = cand.get("functional_potency") if isinstance(cand.get("functional_potency"), dict) else {}
            func_metrics = func.get("metrics") if isinstance(func.get("metrics"), dict) else {}
            metric_keys.extend(sorted([str(k) for k in func_metrics.keys() if str(k).strip()]))
            ptrs: List[Dict[str, Any]] = []
            for mk in sorted(set(metric_keys)):
                ptrs.extend(_why_pointer_list_for_metric_ref(metric_key=mk, ev=(used_by_metric or {}).get(mk)))
            shortlisting_evidence["ranked_candidates"].append(
                {
                    "candidate_id": candidate_id,
                    "evidence": sorted(
                        ptrs,
                        key=lambda x: (
                            str(x.get("kind") or ""),
                            int(x.get("id") or 0),
                            str(x.get("field") or ""),
                            str(x.get("metric_key") or ""),
                        ),
                    ),
                }
            )
        shortlisting_evidence["ranked_candidates"] = sorted(
            shortlisting_evidence["ranked_candidates"],
            key=lambda x: str(x.get("candidate_id") or ""),
        )

    ranking_evidence: Dict[str, Any] = {"candidates": []}
    if isinstance(ranking, dict):
        metric_src = (
            selection_provenance.get("metric_source_batch_ids")
            if isinstance(selection_provenance.get("metric_source_batch_ids"), dict)
            else {}
        )
        for cand in (ranking.get("candidates") or []):
            if not isinstance(cand, dict):
                continue
            cid = cand.get("candidate_id")
            ctype = str(cand.get("candidate_type") or "")
            ptrs: List[Dict[str, Any]] = []
            if ctype == "batch":
                try:
                    cid_i = int(cid)
                except Exception:
                    cid_i = None
                if cid_i is not None:
                    for mk in sorted([str(k) for k in (used_by_metric or {}).keys()]):
                        ev = (used_by_metric or {}).get(mk)
                        if ev is None:
                            continue
                        ev_drid = getattr(ev, "data_record_id", None)
                        ev_mid = getattr(ev, "measurement_id", None)
                        if int(metric_src.get(mk)) == cid_i if (mk in metric_src and str(metric_src.get(mk)).isdigit()) else True:
                            ptrs.extend(_why_pointer_list_for_metric_ref(metric_key=mk, ev=ev))
                    ptrs.append({"kind": "ranking_candidate", "id": cid_i, "field": "candidate_id", "candidate_type": ctype})
            ranking_evidence["candidates"].append(
                {
                    "candidate_id": cid,
                    "candidate_type": ctype,
                    "evidence": sorted(
                        ptrs,
                        key=lambda x: (
                            str(x.get("kind") or ""),
                            int(x.get("id") or 0),
                            str(x.get("field") or ""),
                            str(x.get("metric_key") or ""),
                        ),
                    ),
                }
            )
        ranking_evidence["candidates"] = sorted(
            ranking_evidence["candidates"],
            key=lambda x: (str(x.get("candidate_type") or ""), int(x.get("candidate_id") or 0)),
        )

    return {
        "gates": gate_evidence,
        "readiness": readiness_evidence,
        "shortlisting": shortlisting_evidence,
        "ranking": ranking_evidence,
    }
def _sha256_of_stable_json(obj: Any) -> str:
    return hashlib.sha256(stable_json_dumps(obj).encode("utf-8")).hexdigest()


def _ignored_reason_key(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, dict):
        return str(x.get("reason_key") or "")
    return str(getattr(x, "reason_key", "") or "")


def _is_comparable_from_output(out: Dict[str, Any]) -> bool:
    comp = out.get("comparability") if isinstance(out, dict) else {}
    if isinstance(comp, dict) and "is_comparable" in comp:
        try:
            return bool(comp.get("is_comparable"))
        except Exception:
            pass
    summary = comp.get("summary") if isinstance(comp, dict) else {}
    high = summary.get("high_severity_count") if isinstance(summary, dict) else 0
    try:
        if int(high) > 0:
            return False
    except Exception:
        pass
    conf = out.get("confidence_degradation") if isinstance(out, dict) else {}
    if isinstance(conf, dict) and bool(conf.get("triggered")):
        return False
    return True


def _derive_drift_type(*, out: Dict[str, Any], inputs_obj: Dict[str, Any]) -> str:
    drift_ctx = inputs_obj.get("drift_context") if isinstance(inputs_obj, dict) else None
    if not isinstance(drift_ctx, dict):
        return "NO_CHANGE"

    prev_e = str(drift_ctx.get("prev_evidence_fingerprint") or "")
    prev_p = str(drift_ctx.get("prev_policy_semantics_hash") or "")
    if not prev_e and not prev_p:
        return "NO_CHANGE"

    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    current_p = str(policy.get("policy_semantics_hash") or "")
    prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
    integ = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}
    current_e = str(integ.get("evidence_fingerprint") or "")

    if not current_e or not current_p:
        return "INCOMPARABLE"

    if not _is_comparable_from_output(out):
        return "INCOMPARABLE"

    evidence_changed = current_e != prev_e
    policy_changed = current_p != prev_p

    if not evidence_changed and not policy_changed:
        return "NO_CHANGE"
    if evidence_changed and not policy_changed:
        return "EVIDENCE_ONLY"
    if policy_changed and not evidence_changed:
        return "POLICY_ONLY"
    return "BOTH"


def _derive_state_transition(*, out: Dict[str, Any], inputs_obj: Dict[str, Any]) -> Optional[Dict[str, str]]:
    drift_ctx = inputs_obj.get("drift_context") if isinstance(inputs_obj, dict) else None
    if not isinstance(drift_ctx, dict):
        return None
    from_state = str(drift_ctx.get("prev_decision_state") or "")
    if not from_state:
        return None
    to_state = str(out.get("decision_state") or "")
    if not to_state:
        return None

    drift_type = str(out.get("drift_type") or "")
    if drift_type == "INCOMPARABLE":
        trigger = "INCOMPARABLE"
    elif from_state == to_state:
        trigger = "NONE"
    elif drift_type == "EVIDENCE_ONLY":
        trigger = "EVIDENCE"
    elif drift_type == "POLICY_ONLY":
        trigger = "POLICY"
    elif drift_type == "BOTH":
        trigger = "BOTH"
    else:
        trigger = "NONE"

    return {"from_state": from_state, "to_state": to_state, "trigger": trigger}


def _compute_di_from_used_by_metric(
    db: Session,
    *,
    di_in: DIInput,
    pol: Any,
    used_by_metric: Dict[str, Any],
    inputs_obj: Dict[str, Any],
    ignored: Optional[List[Any]] = None,
    warnings: Optional[List[Dict[str, Any]]] = None,
    selection_provenance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute the DI output from `used_by_metric`.

    This function is intentionally the *single* source of truth for:
    - template evaluation
    - SoE packs
    - readiness + comparability integration
    - integrity hashes

    Callers must provide the authoritative `inputs_obj` that should be used
    for integrity hashing (runner builds it; anchored replay uses the stored one).
    """

    ignored = _normalize_ignored(ignored or [])
    warnings = warnings or []
    selection_provenance = selection_provenance or {}

    template_entry = resolve_template_entry(
        decision_key=di_in.decision_key,
        template_key=getattr(pol, "template_key", "") or "",
    )
    evaluate_fn = template_entry["evaluate"]
    expected_eval_version = str(template_entry.get("evaluator_version") or "")
    enforce_value_functions_template = bool(template_entry.get("enforce_value_functions"))

    metric_evaluations, interpretation_gap_flags = derive_metric_evaluations(
        policy_body=(pol.policy_body or {}),
        used_by_metric=used_by_metric,
        context=di_in.context or {},
    )
    evaluator_version = str(inputs_obj.get("evaluator_version") or expected_eval_version)
    enforce_value_functions = enforce_value_functions_template and evaluator_version == expected_eval_version
    value_fn_reason = _value_functions_enforcement_reason_for_compute(
        template_flag_enabled=enforce_value_functions_template,
        evaluator_version_expected=expected_eval_version,
        evaluator_version_actual=evaluator_version,
    )
    templ = evaluate_fn(
        used_by_metric=used_by_metric,
        policy=pol.policy_body,
        context=di_in.context or {},
        metric_evaluations=(metric_evaluations if enforce_value_functions else {}),
        enforce_value_functions=enforce_value_functions,
    )

    # strict-mode cannot_assess heuristic: nothing usable and strict QC blocked candidates
    strict_blocked = (
        (di_in.qc_mode == "strict")
        and (len(used_by_metric) == 0)
        and any(_ignored_reason_key(ig) in ("qc_unreviewed_strict", "qc_failed") for ig in ignored)
    )

    decision_state = str(templ.get("decision_state") or "")
    if strict_blocked:
        decision_state = "cannot_assess"
        blockers = templ.get("blockers")
        if isinstance(blockers, list):
            blockers.insert(
                0,
                {
                    "blocker_key": "unreviewed_qc_required_metric",
                    "detail": {"qc_mode": "strict", "note": "No acceptable evidence under strict QC."},
                },
            )
        else:
            templ["blockers"] = [
                {
                    "blocker_key": "unreviewed_qc_required_metric",
                    "detail": {"qc_mode": "strict", "note": "No acceptable evidence under strict QC."},
                }
            ]

    # State of Evidence packs (additive)
    if di_in.scope_type == "molecule":
        sp = selection_provenance or {}
        batch_ids = sp.get("batch_ids_ordered") or sp.get("batch_ids_all") or []
        soe_v0_2 = build_soe_v0_2_molecule(
            db,
            molecule_id=int(di_in.scope_id),
            batch_ids=batch_ids,
            decision_key=di_in.decision_key,
            policy_body=(pol.policy_body or {}),
            used_by_metric=used_by_metric,
            ignored=ignored,
            warnings=warnings,
            qc_mode=di_in.qc_mode,
            context=di_in.context or {},
        )
        soe_v0_3 = build_soe_v0_3_molecule(
            db,
            molecule_id=int(di_in.scope_id),
            batch_ids=batch_ids,
            as_of_ts=di_in.as_of_ts,
            qc_mode=di_in.qc_mode,
            policy_body=(pol.policy_body or {}),
            used_by_metric=used_by_metric,
            ignored=ignored,
        )
    else:
        soe_v0_2 = build_soe_v0_2(
            db,
            batch_id=int(di_in.scope_id),
            decision_key=di_in.decision_key,
            policy_body=(pol.policy_body or {}),
            used_by_metric=used_by_metric,
            ignored=ignored,
            warnings=warnings,
            qc_mode=di_in.qc_mode,
            context=di_in.context or {},
        )
        soe_v0_3 = build_soe_v0_3(
            db,
            batch_id=int(di_in.scope_id),
            as_of_ts=di_in.as_of_ts,
            qc_mode=di_in.qc_mode,
            policy_body=(pol.policy_body or {}),
            used_by_metric=used_by_metric,
            ignored=ignored,
        )

    # Catalog reference comes from inputs_obj (runner is authoritative).
    catalog_id = str(inputs_obj.get("catalog_id") or "")
    catalog_version = str(inputs_obj.get("catalog_version") or "")
    catalog_hash = str(inputs_obj.get("catalog_hash") or "")

    # Catalog-driven experiment suggestions (deterministic; no scoring)
    experiment_suggestions, recommended_experiments = build_experiment_suggestions(
        blockers=(templ.get("blockers") or []),
        risk_flags=((templ.get("risk_flags") or []) + (interpretation_gap_flags or [])),
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        allow_recommended_list=True,
    )

    out: Dict[str, Any] = {
        "decision_state": decision_state,
        "policy": {
            "policy_id": pol.policy_id,
            "policy_name": pol.name,
            "policy_version": pol.version,
            "policy_schema_version": pol.schema_version,
            "policy_semantics_hash": pol.policy_semantics_hash,
            "policy_package_hash": pol.policy_package_hash,
            "name": pol.name,
            "version": pol.version,
            "hash": pol.policy_semantics_hash,
            "source": pol.source_name,
            "changelog": pol.changelog if pol.changelog is not None else [],
        },
        "engine": {
            "engine_id": str(inputs_obj.get("engine_id") or ""),
            "schema_version": str(inputs_obj.get("schema_version") or ""),
            "selector_version": str(inputs_obj.get("selector_version") or ""),
            "evaluator_version": str(inputs_obj.get("evaluator_version") or ""),
            "evaluation_version": str(inputs_obj.get("evaluator_version") or ""),
            "code_version": PSI_VERSION,
        },
        "provenance": {
            "as_of_ts": di_in.as_of_ts,
            "qc_mode": di_in.qc_mode,
            "selection_semantics_version": str(inputs_obj.get("selection_semantics_version") or ""),
            "decision_template": {
                "template_key": str(inputs_obj.get("template_key") or ""),
                "template_name": str(inputs_obj.get("template_name") or inputs_obj.get("template_key") or ""),
            },
            "decision_scope": {
                "scope_type": str(di_in.scope_type or ""),
                "scope_id": int(di_in.scope_id),
            },
            "policy_ref": {
                "policy_name": str(getattr(pol, "name", "") or ""),
                "policy_version": str(getattr(pol, "version", "") or ""),
                "policy_semantics_hash": str(getattr(pol, "policy_semantics_hash", "") or ""),
                "policy_package_hash": str(getattr(pol, "policy_package_hash", "") or ""),
            },
            "experiment_catalog": {"catalog_id": catalog_id, "catalog_version": catalog_version, "catalog_hash": catalog_hash},
            "selection_semantics": {
                "ignore_for_model": "always_ignored",
                "outliers": "not_dropped_in_v0_1",
                "primary": "is_primary_first_else_newest_timestamp",
            },
            "selection_provenance": selection_provenance,
            "inputs_fingerprint": {
                "decision_key": di_in.decision_key,
                "scope_type": di_in.scope_type,
                "scope_id": int(di_in.scope_id),
                "context_keys": sorted(list((di_in.context or {}).keys())),
            },
        },
        "state_of_evidence": {
            "used": {str(k): _to_dict(used_by_metric[k]) for k in sorted([str(k) for k in used_by_metric.keys()])},
            "ignored_evidence": [_to_dict(ig) for ig in ignored],
            "warnings": warnings,
            "soe_v0_2": soe_v0_2,
            "soe_v0_3": soe_v0_3,
        },
        "gates": [_to_dict(g) for g in (templ.get("gates") or [])],
        "blockers": templ.get("blockers") or [],
        "risk_flags": (templ.get("risk_flags") or []) + (interpretation_gap_flags or []),
        "risk_flags_enriched": derive_risk_flags_enriched(
            risk_flags=(templ.get("risk_flags") or []) + (interpretation_gap_flags or []),
            used_by_metric=used_by_metric,
            policy_body=(pol.policy_body or {}),
            policy_package=(pol.package or {}),
        ),
        "experiment_suggestions": experiment_suggestions,
        "measurement_ids_used": sorted([
            int(mid)
            for mid in [
                (ev.get("measurement_id") if isinstance(ev, dict) else getattr(ev, "measurement_id", None))
                for ev in used_by_metric.values()
            ]
            if mid is not None and str(mid).strip() and int(mid) > 0
        ]),
    }
    # Governance hardening (w47): weighted ranking is not part of canonical DI output.
    # Deterministic shortlisting/tie-break remains under `shortlisting`.
    if metric_evaluations:
        out["metric_evaluations"] = metric_evaluations
    if recommended_experiments:
        out["recommended_experiments"] = recommended_experiments
    if _should_emit_value_functions_enforced(inputs_obj):
        out["value_functions_enforced"] = bool(enforce_value_functions)
        out["value_functions_enforcement_reason"] = str(value_fn_reason)

    emit_context_branch_surface = _policy_supports_context_branch_surface(pol)
    if emit_context_branch_surface:
        dep_graph = template_dependency_graph()
        out["template_dependency_graph"] = dep_graph
        prov_obj = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
        prov_obj = dict(prov_obj)
        prov_obj["template_dependency_graph"] = dep_graph
        out["provenance"] = prov_obj
    gate_outcomes = derive_gate_outcomes(
        policy_body=(pol.policy_body or {}),
        gate_results=templ.get("gates") or [],
        used_by_metric=used_by_metric,
        inputs_context=(di_in.context if isinstance(di_in.context, dict) else {}),
        emit_context_branch_surface=emit_context_branch_surface,
    )
    if emit_context_branch_surface:
        ctx_knobs = (
            ((pol.package or {}).get("template_structure") or {}).get("context_knobs")
            if isinstance(getattr(pol, "package", None), dict)
            else []
        )
        knob_keys = [str(x) for x in (ctx_knobs or []) if str(x).strip()]
        input_ctx = di_in.context if isinstance(di_in.context, dict) else {}
        out["context_evaluation"] = {
            "policy_version": str(getattr(pol, "version", "") or ""),
            "inputs": {k: input_ctx.get(k) for k in knob_keys},
            "gate_branches": [
                {
                    "gate_key": gk,
                    "branch": dict((gate_outcomes.get(gk) or {}).get("context_branch") or {}),
                }
                for gk in sorted([str(k) for k in gate_outcomes.keys()])
                if isinstance((gate_outcomes.get(gk) or {}).get("context_branch"), dict)
            ],
        }

    readiness = derive_readiness(
        decision_state=decision_state,
        decision_key=di_in.decision_key,
        policy_body=(pol.policy_body or {}),
        gate_results=templ.get("gates") or [],
        templ_blockers=templ.get("blockers") or [],
        used_by_metric=used_by_metric,
        ignored=ignored,
        warnings=warnings,
        qc_mode=di_in.qc_mode,
    )

    if di_in.scope_type == "molecule":
        sp = selection_provenance or {}
        batch_ids = sp.get("batch_ids_ordered") or sp.get("batch_ids_all") or []
        comp_pack = compute_comparability_for_batches(
            db,
            batch_ids=batch_ids,
            as_of_ts=di_in.as_of_ts,
            metric_alias_map=(pol.policy_body.get("metric_alias_map") or {}) if isinstance(pol.policy_body, dict) else {},
            policy_body=(pol.policy_body or {}) if isinstance(pol.policy_body, dict) else {},
        )
    else:
        comp_pack = compute_comparability(
            db,
            batch_id=int(di_in.scope_id),
            as_of_ts=di_in.as_of_ts,
            metric_alias_map=(pol.policy_body.get("metric_alias_map") or {}) if isinstance(pol.policy_body, dict) else {},
            policy_body=(pol.policy_body or {}) if isinstance(pol.policy_body, dict) else {},
        )
    comparability = comp_pack.get("comparability") or {"metric_level": [], "qc_coherence": [], "summary": {"total_flags": 0, "high_severity_count": 0}}
    confidence_degradation = comp_pack.get("confidence_degradation") or {"triggered": False, "reasons": []}

    # Readiness integration is additive-only: assumptions + optional blocking_reasons if policy says block.
    ra = (comp_pack.get("readiness_additions") or {})
    if isinstance(readiness, dict):
        if isinstance(ra.get("assumptions"), list):
            readiness["assumptions"] = sorted(list(set((readiness.get("assumptions") or []) + ra.get("assumptions"))))
        if isinstance(ra.get("blocking_reasons"), list):
            readiness["blocking_reasons"] = sorted(list(set((readiness.get("blocking_reasons") or []) + ra.get("blocking_reasons"))))

    out["gate_outcomes"] = gate_outcomes
    out["readiness"] = readiness
    out["comparability"] = comparability
    out["confidence_degradation"] = confidence_degradation
    out["coverage_fingerprint"] = _sha256_of_stable_json(
        coverage_fingerprint_payload(readiness=readiness, gate_outcomes=gate_outcomes)
    )
    out["suggestions"] = derive_suggestions(gate_outcomes=gate_outcomes, readiness=readiness, ignored=ignored)

    shortlisting = derive_shortlisting(
        policy_body=(pol.policy_body or {}),
        decision_state=decision_state,
        readiness=readiness if isinstance(readiness, dict) else {},
        gate_outcomes=gate_outcomes if isinstance(gate_outcomes, dict) else {},
        blockers=templ.get("blockers") or [],
        comparability=comparability if isinstance(comparability, dict) else {},
        metric_evaluations=metric_evaluations if isinstance(metric_evaluations, dict) else {},
        evidence_summary=(
            (soe_v0_3.get("evidence_summary") if isinstance(soe_v0_3, dict) else [])
            if isinstance(soe_v0_3, dict)
            else []
        ),
        emit_v0_4_extensions=emit_context_branch_surface,
        scope_type=di_in.scope_type,
        scope_id=int(di_in.scope_id),
    )
    if shortlisting is not None:
        out["shortlisting"] = shortlisting
    if emit_context_branch_surface:
        out["scope_semantics"] = _build_scope_semantics(
            di_in=di_in,
            shortlisting=(shortlisting if isinstance(shortlisting, dict) else None),
            selection_provenance=(selection_provenance if isinstance(selection_provenance, dict) else {}),
        )

    out["why_evidence"] = _build_why_evidence(
        out=out,
        used_by_metric=used_by_metric,
        selection_provenance=selection_provenance if isinstance(selection_provenance, dict) else {},
    )

    # Integrity (canonical, additive-only)
    evidence_ids = sorted([ev.measurement_id for ev in used_by_metric.values()])
    prov = out.get("provenance")
    if isinstance(prov, dict):
        integrity = {"evidence_fingerprint": compute_evidence_fingerprint(used_by_metric=used_by_metric)}
        prov["integrity"] = integrity

    # Comparability contract fields (additive)
    comp_obj = out.get("comparability") if isinstance(out.get("comparability"), dict) else {}
    comp_obj = dict(comp_obj)
    conf = out.get("confidence_degradation") if isinstance(out.get("confidence_degradation"), dict) else {}
    high = 0
    if isinstance(comp_obj.get("summary"), dict):
        try:
            high = int(comp_obj.get("summary", {}).get("high_severity_count") or 0)
        except Exception:
            high = 0
    triggered = bool(conf.get("triggered")) or high > 0
    comp_obj["is_comparable"] = not bool(triggered)
    comp_obj["reason"] = "confidence_degradation" if triggered else "ok"

    drift_ctx = inputs_obj.get("drift_context") if isinstance(inputs_obj, dict) else None
    prev_e = str(drift_ctx.get("prev_evidence_fingerprint") or "") if isinstance(drift_ctx, dict) else ""
    prev_p = str(drift_ctx.get("prev_policy_semantics_hash") or "") if isinstance(drift_ctx, dict) else ""
    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    current_p = str(policy.get("policy_semantics_hash") or "")
    integ_cur = prov.get("integrity") if isinstance(prov, dict) and isinstance(prov.get("integrity"), dict) else {}
    current_e = str(integ_cur.get("evidence_fingerprint") or "")
    comp_obj["policy_semantics_hash_changed"] = bool(prev_p and current_p and prev_p != current_p)
    comp_obj["evidence_fingerprint_changed"] = bool(prev_e and current_e and prev_e != current_e)
    out["comparability"] = comp_obj

    out["drift_type"] = _derive_drift_type(out=out, inputs_obj=inputs_obj)
    st = _derive_state_transition(out=out, inputs_obj=inputs_obj)
    if isinstance(st, dict):
        out["state_transition"] = st

    if isinstance(prov, dict):
        integrity = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}
        integrity = dict(integrity)
        integrity["snapshot_content_hash"] = compute_snapshot_content_hash(
            inputs_obj=inputs_obj,
            outputs_obj=out,
            evidence_ids=evidence_ids,
        )
        integrity["decision_output_hash"] = compute_decision_output_hash(inputs_obj=inputs_obj, outputs_obj=out)
        integrity["decision_output_hash_v2"] = compute_decision_output_hash_v2(inputs_obj=inputs_obj, outputs_obj=out)
        prov["integrity"] = integrity

    return out
