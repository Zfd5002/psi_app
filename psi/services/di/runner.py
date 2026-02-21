from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.di.catalog import load_catalog
from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput
from psi.core.models import DecisionSnapshot, Program
from psi.core.utils import now_utc
from psi.services.di.selection import select_batch_measurements
from psi.services.di.templates.advance_to_in_vivo import evaluate as eval_advance_to_in_vivo
from psi.services.di.eval import derive_gate_outcomes, derive_readiness
from psi.services.di.comparability import compute_comparability
from psi.services.di.enrich import (
    build_soe_v0_2,
    build_soe_v0_3,
    coverage_fingerprint_payload,
    derive_risk_flags_enriched,
    derive_suggestions,
)
from psi.services.di.integrity import compute_evidence_fingerprint, compute_snapshot_content_hash
from psi.version import PSI_VERSION


def _stable_json(obj: Any) -> str:
    # Deterministic snapshot serialization for identical inputs/DB state.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


# DI snapshot contract identifiers (stable, explicit, portable)
ENGINE_KEY = "di"
ENGINE_ID = "di.engine.v0_1"
SNAPSHOT_SCHEMA_VERSION = "di.snapshot.v0_1"
SELECTOR_VERSION = "di.selector.v0_1"
EVALUATOR_VERSION = "di.template.advance_to_in_vivo.v0_1"

# explicit selection semantics version (constitution-locked)
DI_SELECTION_SEMANTICS_VERSION = "di.selection.v0_1"

# Policy package schema allowlist (governance guardrail)
ALLOWED_POLICY_SCHEMA_VERSIONS = {"di.policy_package.v0_1"}


def _sha256_of_stable_json(obj: Any) -> str:
    s = _stable_json(obj)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _parse_asof_to_utc_naive(ts: Optional[str]) -> Optional[_dt.datetime]:
    if not ts:
        return None
    t = str(ts).strip()
    if not t:
        return None
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(t)
    except Exception:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return dt


def _policy_schema_mismatch_output(*, di_input: DIInput, pol: Any, mismatch: str) -> Dict[str, Any]:
    # Deterministic NOT_READY snapshot payload that does not raise.
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
            "engine_id": ENGINE_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "selector_version": SELECTOR_VERSION,
            "evaluator_version": EVALUATOR_VERSION,
            "evaluation_version": EVALUATOR_VERSION,
            "code_version": PSI_VERSION,
        },
        "provenance": {
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "selection_semantics_version": DI_SELECTION_SEMANTICS_VERSION,
            "experiment_catalog": {"catalog_id": "", "catalog_version": "", "catalog_hash": ""},
            "selection_provenance": {},
            "inputs_fingerprint": {
                "decision_key": di_input.decision_key,
                "scope_type": di_input.scope_type,
                "scope_id": di_input.scope_id,
                "context_keys": sorted(list((di_input.context or {}).keys())),
            },
        },
        "state_of_evidence": {
            "used": {},
            "ignored_evidence": [],
            "warnings": [
                {
                    "kind": "policy_schema_mismatch",
                    "detail": {
                        "policy_schema_version": getattr(pol, "schema_version", ""),
                        "allowed": sorted(list(ALLOWED_POLICY_SCHEMA_VERSIONS)),
                        "mismatch": mismatch,
                    },
                }
            ],
        },
        "gates": [],
        "blockers": [
            {
                "blocker_key": "policy_schema_mismatch",
                "detail": {
                    "policy_schema_version": getattr(pol, "schema_version", ""),
                    "allowed": sorted(list(ALLOWED_POLICY_SCHEMA_VERSIONS)),
                },
            }
        ],
        "risk_flags": [
            {
                "risk_flag": "policy_schema_mismatch",
                "detail": {"note": "Policy package schema version is not supported by this PSI build."},
            }
        ],
        "risk_flags_enriched": [
            {
                "key": "policy_schema_mismatch",
                "category": "governance",
                "severity": "high",
                "related_metrics": [],
                "explanation": "Policy package schema version is not supported by this PSI build.",
            }
        ],
        "experiment_suggestions": {},
        "measurement_ids_used": [],
        "gate_outcomes": {},
        "readiness": {
            "state": "blocked",
            "blockers": [
                {
                    "key": "policy_schema_mismatch",
                    "severity": "high",
                    "metrics": [],
                    "gates": [],
                    "explanation": "Unsupported policy package schema version.",
                }
            ],
            "coverage": {"required_present": 0, "required_total": 0, "optional_present": 0, "optional_total": 0, "coverage_ratio": 0.0},
            "qc_confidence": {"qc_mode": str(di_input.qc_mode), "reviewed_required_present": 0, "unreviewed_required_present": 0, "notes": []},
            "comparability": {"method_incomparable_metrics": [], "notes": []},
            "decision_context": str(di_input.decision_key),
            "readiness_level": "blocked",
            "blocking_gates": [],
            "blocking_reasons": ["Unsupported policy package schema version."],
            "assumptions": [],
            "required_next_steps": [],
        },
        "coverage_fingerprint": _sha256_of_stable_json(
            coverage_fingerprint_payload(readiness={"blockers": [], "coverage": {"required_present": 0, "required_total": 0, "optional_present": 0, "optional_total": 0, "coverage_ratio": 0.0}, "comparability": {"method_incomparable_metrics": [], "notes": []}}, gate_outcomes={})
        ),
        "suggestions": [],
    }


def run_di(db: Session, *, di_input: DIInput, policy_path: Path) -> Dict[str, Any]:
    pol = load_policy(policy_path)
    if pol.decision_key != di_input.decision_key:
        raise ValueError(f"Policy decision_key mismatch: policy={pol.decision_key} input={di_input.decision_key}")

    if di_input.scope_type != "batch":
        raise ValueError("DI v0.1 supports scope_type=batch only")

    if di_input.decision_key != "advance_to_in_vivo":
        raise ValueError("DI v0.1 supports decision_key=advance_to_in_vivo only")

    program_id, molecule_id = _resolve_snapshot_lineage(db, batch_id=int(di_input.scope_id))

    res = compute_di_output(db, di_input=di_input, pol=pol, policy_path=policy_path)
    out = res["output"]
    inputs_obj = res["inputs_obj"]
    evidence_ids = res["evidence_ids"]
    rules_version = res["rules_version"]

    snap = DecisionSnapshot(
        program_id=int(program_id),
        molecule_id=molecule_id,
        batch_id=int(di_input.scope_id),
        decision_key=di_input.decision_key,
        rules_version=rules_version,
        engine_key=ENGINE_KEY,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        inputs_json=_stable_json(inputs_obj),
        outputs_json=_stable_json(out),
        evidence_ids_json=_stable_json(sorted(list(evidence_ids))),
        as_of_ts=_parse_asof_to_utc_naive(di_input.as_of_ts),
        created_at=now_utc(),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    return {"snapshot_id": snap.id, "output": out}


def _resolve_snapshot_lineage(db: Session, *, batch_id: int) -> Tuple[int, Optional[int]]:
    """Resolve program_id + molecule_id for snapshot lineage."""

    row = db.execute(
        text(
            """
            SELECT
              b.id as batch_id,
              b.molecule_id as molecule_id,
              m.program_id as program_id
            FROM batches b
            LEFT JOIN molecules m ON m.id=b.molecule_id
            WHERE b.id=:bid
            """
        ),
        {"bid": int(batch_id)},
    ).mappings().first()
    if not row:
        raise KeyError(f"Batch not found: {batch_id}")

    molecule_id = int(row["molecule_id"]) if row.get("molecule_id") is not None else None
    program_id = int(row["program_id"]) if row.get("program_id") is not None else None
    if program_id is None:
        p = db.query(Program).filter(Program.name == "PSI_EXAMPLES").first()
        program_id = int(p.id) if p else 1
    return int(program_id), molecule_id


def compute_di_output(
    db: Session,
    *,
    di_input: DIInput,
    pol: Any,
    policy_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Pure DI computation path.

    IMPORTANT: This function must not persist snapshots or mutate DB state.
    It returns the computed output plus the snapshot inputs payload and evidence ids.
    """

    rules_version = f"{pol.name}:{pol.version}:{pol.policy_semantics_hash[:12]}"

    # Policy governance guardrail: enforce known package schema versions.
    if str(pol.schema_version) not in ALLOWED_POLICY_SCHEMA_VERSIONS:
        out = _policy_schema_mismatch_output(di_input=di_input, pol=pol, mismatch="unknown_policy_schema_version")
        inputs_obj = {
            "decision_key": di_input.decision_key,
            "scope_type": di_input.scope_type,
            "scope_id": di_input.scope_id,
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "context": di_input.context or {},
            "engine_key": ENGINE_KEY,
            "engine_id": ENGINE_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "selector_version": SELECTOR_VERSION,
            "evaluator_version": EVALUATOR_VERSION,
            "selection_semantics_version": DI_SELECTION_SEMANTICS_VERSION,
            "policy_id": pol.policy_id,
            "policy_version": pol.version,
            "policy_name": pol.name,
            "policy_semantics_hash": pol.policy_semantics_hash,
            "policy_package_hash": pol.policy_package_hash,
            "policy_schema_version": pol.schema_version,
            "policy_hash": pol.policy_semantics_hash,
            "policy_source": pol.source_name,
            "policy_json_canonical": pol.policy_body_canonical_json,
            "catalog_id": "",
            "catalog_version": "",
            "catalog_hash": "",
            # Non-authoritative, machine-local metadata (debugging only)
            "policy_path": str(policy_path) if policy_path is not None else "",
        }
        evidence_ids: list[int] = []

        # v1.2.9k integrity
        prov = out.get("provenance")
        if isinstance(prov, dict):
            integrity = {"evidence_fingerprint": compute_evidence_fingerprint(used_by_metric={})}
            integrity["snapshot_content_hash"] = compute_snapshot_content_hash(
                inputs_obj=inputs_obj,
                outputs_obj=out,
                evidence_ids=evidence_ids,
            )
            prov["integrity"] = integrity

        return {"rules_version": rules_version, "inputs_obj": inputs_obj, "output": out, "evidence_ids": evidence_ids}

    sel = select_batch_measurements(
        db,
        batch_id=int(di_input.scope_id),
        as_of_ts=di_input.as_of_ts,
        qc_mode=di_input.qc_mode,
        metric_alias_map=(pol.policy_body.get("metric_alias_map") or {}),
        policy_qc=(pol.policy_body.get("qc_modes") or {}),
    )

    used_by_metric = sel["used_by_metric"]
    ignored = sel["ignored"]
    warnings = sel["warnings"]
    selection_provenance = sel.get("selection_provenance") or {}

    templ = eval_advance_to_in_vivo(used_by_metric=used_by_metric, policy=pol.policy_body, context=di_input.context or {})

    # strict-mode cannot_assess heuristic: nothing usable and strict QC blocked candidates
    strict_blocked = (
        (di_input.qc_mode == "strict")
        and (len(used_by_metric) == 0)
        and any(ig.reason_key in ("qc_unreviewed_strict", "qc_failed") for ig in ignored)
    )

    decision_state = templ["decision_state"]
    if strict_blocked:
        decision_state = "cannot_assess"
        templ["blockers"].insert(
            0,
            {
                "blocker_key": "unreviewed_qc_required_metric",
                "detail": {"qc_mode": "strict", "note": "No acceptable evidence under strict QC."},
            },
        )

    # State of Evidence v0.2 (descriptive extension; no behavior change)
    soe_v0_2 = build_soe_v0_2(
        db,
        batch_id=int(di_input.scope_id),
        decision_key=di_input.decision_key,
        policy_body=(pol.policy_body or {}),
        used_by_metric=used_by_metric,
        ignored=ignored,
        warnings=warnings,
        qc_mode=di_input.qc_mode,
        context=di_input.context or {},
    )

    # State of Evidence v0.3 (additive summary; no evaluation change)
    soe_v0_3 = build_soe_v0_3(
        db,
        batch_id=int(di_input.scope_id),
        as_of_ts=di_input.as_of_ts,
        qc_mode=di_input.qc_mode,
        policy_body=(pol.policy_body or {}),
        used_by_metric=used_by_metric,
        ignored=ignored,
    )

    # Catalog reference + hash (catalog JSON is NOT embedded in snapshots).
    cat_ref = pol.experiment_catalog_ref
    catalog_id = str(cat_ref.get("catalog_id") or "")
    catalog_version = str(cat_ref.get("catalog_version") or "")
    catalog_hash = ""
    if catalog_id and catalog_version:
        cat_path = Path(__file__).resolve().parents[2] / "core" / "di" / "catalogs" / "experiment_catalog_v0_1.json"
        cat = load_catalog(cat_path)
        if cat.catalog_id != catalog_id or cat.catalog_version != catalog_version:
            raise ValueError(
                f"Experiment catalog ref mismatch: policy_ref={catalog_id}:{catalog_version} file={cat.catalog_id}:{cat.catalog_version}"
            )
        catalog_hash = cat.catalog_hash

    # Blocker -> experiment mapping (neutral; sorted/deduped; no prioritization logic)
    experiment_suggestions: Dict[str, Any] = {}
    blocker_suggestions = pol.policy_body.get("blocker_suggestions") if isinstance(pol.policy_body, dict) else {}
    if isinstance(blocker_suggestions, dict):
        for bk, exps in blocker_suggestions.items():
            if isinstance(exps, list):
                seen = set()
                out_list = []
                for x in exps:
                    sx = str(x).strip()
                    if not sx or sx in seen:
                        continue
                    seen.add(sx)
                    out_list.append(sx)
                experiment_suggestions[str(bk)] = sorted(out_list)

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
            "engine_id": ENGINE_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "selector_version": SELECTOR_VERSION,
            "evaluator_version": EVALUATOR_VERSION,
            # additive hardening
            "evaluation_version": EVALUATOR_VERSION,
            "code_version": PSI_VERSION,
        },
        "provenance": {
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "selection_semantics_version": DI_SELECTION_SEMANTICS_VERSION,
            "experiment_catalog": {"catalog_id": catalog_id, "catalog_version": catalog_version, "catalog_hash": catalog_hash},
            "selection_semantics": {
                "ignore_for_model": "always_ignored",
                "outliers": "not_dropped_in_v0_1",
                "primary": "is_primary_first_else_newest_timestamp",
            },
            "selection_provenance": selection_provenance,
            "inputs_fingerprint": {
                "decision_key": di_input.decision_key,
                "scope_type": di_input.scope_type,
                "scope_id": di_input.scope_id,
                "context_keys": sorted(list((di_input.context or {}).keys())),
            },
        },
        "state_of_evidence": {
            "used": {k: v.__dict__ for k, v in used_by_metric.items()},
            "ignored_evidence": [ig.__dict__ for ig in ignored],
            "warnings": warnings,
            "soe_v0_2": soe_v0_2,
            "soe_v0_3": soe_v0_3,
        },
        "gates": [g.__dict__ for g in templ["gates"]],
        "blockers": templ["blockers"],
        "risk_flags": templ["risk_flags"],
        "risk_flags_enriched": derive_risk_flags_enriched(
            risk_flags=templ["risk_flags"],
            used_by_metric=used_by_metric,
            policy_body=(pol.policy_body or {}),
        ),
        "experiment_suggestions": experiment_suggestions,
        "measurement_ids_used": sorted([ev.measurement_id for ev in used_by_metric.values()]),
    }

    gate_outcomes = derive_gate_outcomes(policy_body=(pol.policy_body or {}), gate_results=templ["gates"], used_by_metric=used_by_metric)

    readiness = derive_readiness(
        decision_state=decision_state,
        decision_key=di_input.decision_key,
        policy_body=(pol.policy_body or {}),
        gate_results=templ["gates"],
        templ_blockers=templ["blockers"],
        used_by_metric=used_by_metric,
        ignored=ignored,
        warnings=warnings,
        qc_mode=di_input.qc_mode,
    )

    # v1.2.9j: evidence comparability + QC coherence diagnostics (additive; no behavior change)
    comp_pack = compute_comparability(
        db,
        batch_id=int(di_input.scope_id),
        as_of_ts=di_input.as_of_ts,
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
    out["coverage_fingerprint"] = _sha256_of_stable_json(coverage_fingerprint_payload(readiness=readiness, gate_outcomes=gate_outcomes))

    # v1.2.9i: formalized suggestions (non-ranked; policy-derived only)
    out["suggestions"] = derive_suggestions(gate_outcomes=gate_outcomes, readiness=readiness, ignored=ignored)

    inputs_obj = {
        "decision_key": di_input.decision_key,
        "scope_type": di_input.scope_type,
        "scope_id": di_input.scope_id,
        "as_of_ts": di_input.as_of_ts,
        "qc_mode": di_input.qc_mode,
        "context": di_input.context or {},
        "engine_key": ENGINE_KEY,
        "engine_id": ENGINE_ID,
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "selector_version": SELECTOR_VERSION,
        "evaluator_version": EVALUATOR_VERSION,
        "selection_semantics_version": DI_SELECTION_SEMANTICS_VERSION,
        # Policy packaging
        "policy_id": pol.policy_id,
        "policy_version": pol.version,
        "policy_name": pol.name,
        "policy_semantics_hash": pol.policy_semantics_hash,
        "policy_package_hash": pol.policy_package_hash,
        "policy_schema_version": pol.schema_version,
        # Back-compat fields
        "policy_hash": pol.policy_semantics_hash,
        "policy_source": pol.source_name,
        "policy_json_canonical": pol.policy_body_canonical_json,
        # Experiment catalog reference
        "catalog_id": catalog_id,
        "catalog_version": catalog_version,
        "catalog_hash": catalog_hash,
        # Non-authoritative, machine-local metadata (debugging only)
        "policy_path": str(policy_path) if policy_path is not None else "",
    }

    evidence_ids = sorted([ev.measurement_id for ev in used_by_metric.values()])

    # v1.2.9k integrity (additive only)
    prov = out.get("provenance")
    if isinstance(prov, dict):
        integrity = {"evidence_fingerprint": compute_evidence_fingerprint(used_by_metric=used_by_metric)}
        integrity["snapshot_content_hash"] = compute_snapshot_content_hash(
            inputs_obj=inputs_obj,
            outputs_obj=out,
            evidence_ids=evidence_ids,
        )
        prov["integrity"] = integrity

    return {"rules_version": rules_version, "inputs_obj": inputs_obj, "output": out, "evidence_ids": evidence_ids}
