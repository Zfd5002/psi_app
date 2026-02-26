from __future__ import annotations

from typing import Any, Callable, Dict

from psi.core.di.schema import DIInput
from psi.services.di.enrich import coverage_fingerprint_payload


def build_di_error_output_payload(
    *,
    di_input: DIInput,
    pol: Any,
    evaluator_version: str,
    warning_kind: str,
    warning_detail: Dict[str, Any],
    blocker_key: str,
    blocker_detail: Dict[str, Any],
    risk_flag: str,
    risk_note: str,
    risk_enriched_key: str,
    risk_enriched_explanation: str,
    readiness_blocker_key: str,
    readiness_blocker_explanation: str,
    readiness_blocking_reason: str,
    engine_id: str,
    snapshot_schema_version: str,
    selector_version: str,
    selection_semantics_version: str,
    code_version: str,
    stable_hash_json_fn: Callable[[Any], str],
) -> Dict[str, Any]:
    return {
        "decision_state": "not_ready",
        "policy": {
            "policy_id": getattr(pol, "policy_id", ""),
            "policy_name": getattr(pol, "name", ""),
            "policy_version": getattr(pol, "version", ""),
            "policy_schema_version": getattr(pol, "schema_version", ""),
            "policy_semantics_hash": getattr(pol, "policy_semantics_hash", ""),
            "policy_package_hash": getattr(pol, "policy_package_hash", ""),
            "name": getattr(pol, "name", ""),
            "version": getattr(pol, "version", ""),
            "hash": getattr(pol, "policy_semantics_hash", ""),
            "source": getattr(pol, "source_name", ""),
            "changelog": getattr(pol, "changelog", []) if getattr(pol, "changelog", None) is not None else [],
        },
        "engine": {
            "engine_id": engine_id,
            "schema_version": snapshot_schema_version,
            "selector_version": selector_version,
            "evaluator_version": str(evaluator_version),
            "evaluation_version": str(evaluator_version),
            "code_version": code_version,
        },
        "provenance": {
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "selection_semantics_version": selection_semantics_version,
            "experiment_catalog": {"catalog_id": "", "catalog_version": "", "catalog_hash": ""},
            "selection_provenance": {},
            "inputs_fingerprint": {
                "decision_key": di_input.decision_key,
                "scope_type": di_input.scope_type,
                "scope_id": int(di_input.scope_id),
                "context_keys": sorted(list((di_input.context or {}).keys())),
            },
        },
        "state_of_evidence": {
            "used": {},
            "ignored_evidence": [],
            "warnings": [{"kind": str(warning_kind), "detail": dict(warning_detail or {})}],
        },
        "gates": [],
        "blockers": [{"blocker_key": str(blocker_key), "detail": dict(blocker_detail or {})}],
        "risk_flags": [{"risk_flag": str(risk_flag), "detail": {"note": str(risk_note)}}],
        "risk_flags_enriched": [
            {
                "key": str(risk_enriched_key),
                "category": "governance",
                "severity": "high",
                "related_metrics": [],
                "explanation": str(risk_enriched_explanation),
            }
        ],
        "experiment_suggestions": {},
        "measurement_ids_used": [],
        "gate_outcomes": {},
        "readiness": {
            "state": "blocked",
            "blockers": [
                {
                    "key": str(readiness_blocker_key),
                    "severity": "high",
                    "metrics": [],
                    "gates": [],
                    "explanation": str(readiness_blocker_explanation),
                }
            ],
            "coverage": {"required_present": 0, "required_total": 0, "optional_present": 0, "optional_total": 0, "coverage_ratio": 0.0},
            "qc_confidence": {"qc_mode": str(di_input.qc_mode), "reviewed_required_present": 0, "unreviewed_required_present": 0, "notes": []},
            "comparability": {"method_incomparable_metrics": [], "notes": []},
            "decision_context": str(di_input.decision_key),
            "readiness_level": "blocked",
            "blocking_gates": [],
            "blocking_reasons": [str(readiness_blocking_reason)],
            "assumptions": [],
            "required_next_steps": [],
        },
        "coverage_fingerprint": stable_hash_json_fn(
            coverage_fingerprint_payload(
                readiness={
                    "blockers": [],
                    "coverage": {"required_present": 0, "required_total": 0, "optional_present": 0, "optional_total": 0, "coverage_ratio": 0.0},
                    "comparability": {"method_incomparable_metrics": [], "notes": []},
                },
                gate_outcomes={},
            )
        ),
        "suggestions": [],
    }
