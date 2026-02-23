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
from psi.services.di.templates.advance_to_in_vivo import evaluate as eval_advance_to_in_vivo
from psi.services.di.eval import derive_gate_outcomes, derive_readiness, derive_shortlisting
from psi.services.di.comparability import compute_comparability
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
                out.append(IgnoredEvidence(**ig))
                continue
            except Exception:
                # Fall back to minimal safe representation; keep determinism.
                out.append(IgnoredEvidence(
                    measurement_id=int(ig.get("measurement_id") or 0),
                    data_record_id=int(ig.get("data_record_id") or 0),
                    metric_key=str(ig.get("metric_key") or ""),
                    reason_key=str(ig.get("reason_key") or ""),
                    reason_detail=(str(ig.get("reason_detail")) if ig.get("reason_detail") is not None else None),
                    qc_status=(str(ig.get("qc_status")) if ig.get("qc_status") is not None else None),
                ))
                continue
        # Unknown type: stringify deterministically into reason_detail
        out.append(IgnoredEvidence(
            measurement_id=0,
            data_record_id=0,
            metric_key="",
            reason_key="unknown",
            reason_detail=str(ig),
            qc_status=None,
        ))
    return out
def _stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_of_stable_json(obj: Any) -> str:
    return hashlib.sha256(_stable_json(obj).encode("utf-8")).hexdigest()


def _ignored_reason_key(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, dict):
        return str(x.get("reason_key") or "")
    return str(getattr(x, "reason_key", "") or "")


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

    templ = eval_advance_to_in_vivo(
        used_by_metric=used_by_metric,
        policy=pol.policy_body,
        context=di_in.context or {},
    )

    metric_evaluations, interpretation_gap_flags = derive_metric_evaluations(
        policy_body=(pol.policy_body or {}),
        used_by_metric=used_by_metric,
        context=di_in.context or {},
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
            "used": {str(k): _to_dict(v) for k, v in used_by_metric.items()},
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
    if metric_evaluations:
        out["metric_evaluations"] = metric_evaluations
    if recommended_experiments:
        out["recommended_experiments"] = recommended_experiments

    gate_outcomes = derive_gate_outcomes(
        policy_body=(pol.policy_body or {}),
        gate_results=templ.get("gates") or [],
        used_by_metric=used_by_metric,
    )

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
        scope_type=di_in.scope_type,
        scope_id=int(di_in.scope_id),
    )
    if shortlisting is not None:
        out["shortlisting"] = shortlisting

    # Integrity (canonical, additive-only)
    evidence_ids = sorted([ev.measurement_id for ev in used_by_metric.values()])
    prov = out.get("provenance")
    if isinstance(prov, dict):
        integrity = {"evidence_fingerprint": compute_evidence_fingerprint(used_by_metric=used_by_metric)}
        integrity["snapshot_content_hash"] = compute_snapshot_content_hash(
            inputs_obj=inputs_obj,
            outputs_obj=out,
            evidence_ids=evidence_ids,
        )
        integrity["decision_output_hash"] = compute_decision_output_hash(inputs_obj=inputs_obj, outputs_obj=out)
        integrity["decision_output_hash_v2"] = compute_decision_output_hash_v2(inputs_obj=inputs_obj, outputs_obj=out)
        prov["integrity"] = integrity

    return out
