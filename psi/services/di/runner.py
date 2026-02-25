from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from psi.core.di.catalog import load_experiment_catalog_v0_1
from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput
from psi.core.models import DecisionSnapshot, Molecule, Program
from psi.core.utils import now_utc, stable_json_dumps
from psi.services.di.selection import select_batch_measurements
from psi.services.di.compute import _compute_di_from_used_by_metric
from psi.services.di.enrich import coverage_fingerprint_payload
from psi.services.di.integrity import compute_decision_output_hash, compute_decision_output_hash_v2, compute_evidence_fingerprint, compute_snapshot_content_hash
from psi.services.di.templates.registry import resolve_template_entry
from psi.version import PSI_VERSION


# DI snapshot contract identifiers (stable, explicit, portable)
ENGINE_KEY = "di"
ENGINE_ID = "di.engine.v0_1"
SNAPSHOT_SCHEMA_VERSION = "di.snapshot.v0_1"
SELECTOR_VERSION = "di.selector.v0_1"

# explicit selection semantics version (constitution-locked)
DI_SELECTION_SEMANTICS_VERSION = "di.selection.v0_1"

# Policy package schema allowlist (governance guardrail)
ALLOWED_POLICY_SCHEMA_VERSIONS = {"di.policy_package.v0_1"}


def _sha256_of_stable_json(obj: Any) -> str:
    s = stable_json_dumps(obj)
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


def _policy_schema_mismatch_output(*, di_input: DIInput, pol: Any, mismatch: str, evaluator_version: str) -> Dict[str, Any]:
    # Deterministic NOT_READY snapshot payload that does not raise.
    return _build_di_error_output(
        di_input=di_input,
        pol=pol,
        evaluator_version=evaluator_version,
        warning_kind="policy_schema_mismatch",
        warning_detail={
            "policy_schema_version": getattr(pol, "schema_version", ""),
            "allowed": sorted(list(ALLOWED_POLICY_SCHEMA_VERSIONS)),
            "mismatch": mismatch,
        },
        blocker_key="policy_schema_mismatch",
        blocker_detail={
            "policy_schema_version": getattr(pol, "schema_version", ""),
            "allowed": sorted(list(ALLOWED_POLICY_SCHEMA_VERSIONS)),
        },
        risk_flag="policy_schema_mismatch",
        risk_note="Policy package schema version is not supported by this PSI build.",
        risk_enriched_key="policy_schema_mismatch",
        risk_enriched_explanation="Policy package schema version is not supported by this PSI build.",
        readiness_blocker_key="policy_schema_mismatch",
        readiness_blocker_explanation="Unsupported policy package schema version.",
        readiness_blocking_reason="Unsupported policy package schema version.",
    )


def _build_di_error_output(
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
            "engine_id": ENGINE_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "selector_version": SELECTOR_VERSION,
            "evaluator_version": str(evaluator_version),
            "evaluation_version": str(evaluator_version),
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
                "scope_id": int(di_input.scope_id),
                "context_keys": sorted(list((di_input.context or {}).keys())),
            },
        },
        "state_of_evidence": {
            "used": {},
            "ignored_evidence": [],
            "warnings": [
                {
                    "kind": str(warning_kind),
                    "detail": dict(warning_detail or {}),
                }
            ],
        },
        "gates": [],
        "blockers": [
            {
                "blocker_key": str(blocker_key),
                "detail": dict(blocker_detail or {}),
            }
        ],
        "risk_flags": [
            {
                "risk_flag": str(risk_flag),
                "detail": {"note": str(risk_note)},
            }
        ],
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
        "coverage_fingerprint": _sha256_of_stable_json(
            coverage_fingerprint_payload(readiness={"blockers": [], "coverage": {"required_present": 0, "required_total": 0, "optional_present": 0, "optional_total": 0, "coverage_ratio": 0.0}, "comparability": {"method_incomparable_metrics": [], "notes": []}}, gate_outcomes={})
        ),
        "suggestions": [],
    }


def _unsupported_template_output(
    *,
    di_input: DIInput,
    pol: Any,
    reason: str,
    evaluator_version: str,
) -> Dict[str, Any]:
    detail = {
        "decision_key": di_input.decision_key,
        "template_key": getattr(pol, "template_key", ""),
        "reason": str(reason),
    }
    return _build_di_error_output(
        di_input=di_input,
        pol=pol,
        evaluator_version=evaluator_version,
        warning_kind="unsupported_template",
        warning_detail=detail,
        blocker_key="unsupported_template",
        blocker_detail=detail,
        risk_flag="unsupported_template",
        risk_note="Decision template is not supported by this PSI build.",
        risk_enriched_key="unsupported_template",
        risk_enriched_explanation="Decision template is not supported by this PSI build.",
        readiness_blocker_key="unsupported_template",
        readiness_blocker_explanation="Unsupported decision template.",
        readiness_blocking_reason="Unsupported decision template.",
    )


def _drift_context_for_scope(
    db: Session,
    *,
    decision_key: str,
    program_id: int,
    molecule_id: int | None,
    batch_id: int | None,
) -> Dict[str, Any]:
    cutoff_raw = os.environ.get("PSI_DI_BASELINE_CUTOFF_ISO")
    cutoff_dt = _parse_asof_to_utc_naive(cutoff_raw) if cutoff_raw else None
    if cutoff_raw and cutoff_dt is None:
        print(f"WARNING: invalid PSI_DI_BASELINE_CUTOFF_ISO ignored: {cutoff_raw}", file=sys.stderr)

    q = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.decision_key == str(decision_key))
        .filter(DecisionSnapshot.program_id == int(program_id))
        .filter(DecisionSnapshot.molecule_id == (int(molecule_id) if molecule_id is not None else None))
        .filter(DecisionSnapshot.batch_id == (int(batch_id) if batch_id is not None else None))
        .filter(DecisionSnapshot.superseded_by_snapshot_id.is_(None))
    )
    if cutoff_dt is not None:
        q = q.filter(DecisionSnapshot.created_at <= cutoff_dt)
    prev = q.order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc()).first()
    if not prev:
        return {}
    try:
        out = json.loads(prev.outputs_json or "{}")
    except Exception:
        out = {}
    if not isinstance(out, dict):
        out = {}
    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
    integ = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}
    return {
        "prev_snapshot_id": int(prev.id),
        "prev_policy_semantics_hash": str(policy.get("policy_semantics_hash") or ""),
        "prev_evidence_fingerprint": str(integ.get("evidence_fingerprint") or ""),
        "prev_decision_state": str(out.get("decision_state") or ""),
    }


def _resolve_molecule_lineage(db: Session, *, molecule_id: int) -> int:
    m = db.get(Molecule, int(molecule_id))
    if not m:
        raise KeyError(f"Molecule not found: {molecule_id}")
    program_id = int(getattr(m, "program_id", 0) or 0)
    if program_id <= 0:
        raise ValueError(f"Missing program_id for molecule_id={int(molecule_id)}; cannot resolve lineage")
    return program_id


def _select_batches_for_molecule(db: Session, *, molecule_id: int) -> list[Dict[str, Any]]:
    """Deterministic batch selection for molecule scope.

    Rule:
    - include all batches where batch.molecule_id == molecule_id
    - order by created_at ASC, then id ASC (stable, tie-safe)
    """

    rows = (
        db.execute(
            text(
                """
                SELECT id, created_at
                FROM batches
                WHERE molecule_id = :mid
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"mid": int(molecule_id)},
        )
        .mappings()
        .all()
    )
    out: list[Dict[str, Any]] = []
    for r in rows:
        try:
            bid = int(r.get("id"))
        except Exception:
            continue
        out.append({"batch_id": bid, "created_at": r.get("created_at")})
    return out


def _format_ts(v: Any) -> Optional[str]:
    if v is None:
        return None
    try:
        if hasattr(v, "isoformat"):
            return v.isoformat()
    except Exception:
        pass
    s = str(v).strip()
    return s if s else None


def _sort_ignored_entries(ignored: list[Any]) -> list[Any]:
    def _key(x: Any) -> tuple:
        if isinstance(x, dict):
            return (
                str(x.get("metric_key") or ""),
                int(x.get("measurement_id") or 0),
                int(x.get("data_record_id") or 0),
                str(x.get("reason_key") or ""),
            )
        return (
            str(getattr(x, "metric_key", "") or ""),
            int(getattr(x, "measurement_id", 0) or 0),
            int(getattr(x, "data_record_id", 0) or 0),
            str(getattr(x, "reason_key", "") or ""),
        )

    return sorted(list(ignored or []), key=_key)


def _sort_warning_entries(warnings: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    return sorted([w for w in (warnings or []) if isinstance(w, dict)], key=lambda w: stable_json_dumps(w))


def run_di(db: Session, *, di_input: DIInput, policy_path: Path) -> Dict[str, Any]:
    pol = load_policy(policy_path)
    if pol.decision_key != di_input.decision_key:
        raise ValueError(f"Policy decision_key mismatch: policy={pol.decision_key} input={di_input.decision_key}")

    if di_input.scope_type not in ("batch", "molecule"):
        raise ValueError(f"Unknown DI scope_type: {di_input.scope_type}")

    program_id: int
    molecule_id: Optional[int]
    batch_id: Optional[int]
    if di_input.scope_type == "batch":
        program_id, molecule_id = _resolve_snapshot_lineage(db, batch_id=int(di_input.scope_id))
        batch_id = int(di_input.scope_id)
    else:
        molecule_id = int(di_input.scope_id)
        program_id = _resolve_molecule_lineage(db, molecule_id=molecule_id)
        batch_id = None

    drift_ctx = _drift_context_for_scope(
        db,
        decision_key=di_input.decision_key,
        program_id=program_id,
        molecule_id=molecule_id,
        batch_id=batch_id,
    )
    res = compute_di_output(db, di_input=di_input, pol=pol, policy_path=policy_path, drift_context=drift_ctx)
    out = res["output"]
    inputs_obj = res["inputs_obj"]
    evidence_ids = res["evidence_ids"]
    rules_version = res["rules_version"]



    # v1.2.9q: supersede prior ACTIVE snapshots for this exact scope, transactionally.
    active_ids = [
        int(r[0])
        for r in db.execute(
            text(
                '''
                SELECT id
                FROM decision_snapshots
                WHERE decision_key = :dk
                  AND program_id = :pid
                  AND COALESCE(molecule_id, 0) = COALESCE(:mid, 0)
                  AND COALESCE(batch_id, 0) = COALESCE(:bid, 0)
                  AND (is_superseded IS NULL OR is_superseded = 0)
                '''
            ),
            {"dk": di_input.decision_key, "pid": int(program_id), "mid": molecule_id, "bid": (int(batch_id) if batch_id is not None else None)},
        ).fetchall()
    ]

    if active_ids:
        q = text(
            '''
            UPDATE decision_snapshots
            SET is_superseded = 1,
                superseded_at = CURRENT_TIMESTAMP,
                superseded_by_snapshot_id = NULL
            WHERE id IN :ids
            '''
        ).bindparams(bindparam("ids", expanding=True))
        db.execute(q, {"ids": list(active_ids)})

    snap = DecisionSnapshot(
        program_id=int(program_id),
        molecule_id=molecule_id,
        batch_id=(int(batch_id) if batch_id is not None else None),
        decision_key=di_input.decision_key,
        rules_version=rules_version,
        engine_key=ENGINE_KEY,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        is_superseded=0,
        inputs_json=stable_json_dumps(inputs_obj),
        outputs_json=stable_json_dumps(out),
        evidence_ids_json=stable_json_dumps(sorted(list(evidence_ids))),
        as_of_ts=_parse_asof_to_utc_naive(di_input.as_of_ts),
        created_at=now_utc(),
    )
    db.add(snap)
    db.flush()

    if active_ids:
        q = text(
            '''
            UPDATE decision_snapshots
            SET superseded_by_snapshot_id = :new_id
            WHERE id IN :ids
            '''
        ).bindparams(bindparam("ids", expanding=True))
        db.execute(q, {"new_id": int(snap.id), "ids": list(active_ids)})

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
        raise ValueError(f"Missing program_id for batch_id={int(batch_id)}; cannot resolve lineage")
    return int(program_id), molecule_id


def compute_di_output(
    db: Session,
    *,
    di_input: DIInput,
    pol: Any,
    policy_path: Optional[Path] = None,
    drift_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pure DI computation path.

    IMPORTANT: This function must not persist snapshots or mutate DB state.
    It returns the computed output plus the snapshot inputs payload and evidence ids.
    """

    rules_version = f"{pol.name}:{pol.version}:{pol.policy_semantics_hash[:12]}"

    template_entry = None
    template_error = ""
    try:
        template_entry = resolve_template_entry(
            decision_key=di_input.decision_key,
            template_key=getattr(pol, "template_key", "") or "",
        )
    except Exception as exc:
        template_entry = None
        template_error = str(exc)

    evaluator_version = str((template_entry or {}).get("evaluator_version") or "unknown")

    # Policy governance guardrail: enforce known package schema versions.
    if str(pol.schema_version) not in ALLOWED_POLICY_SCHEMA_VERSIONS:
        out = _policy_schema_mismatch_output(
            di_input=di_input,
            pol=pol,
            mismatch="unknown_policy_schema_version",
            evaluator_version=evaluator_version,
        )
        inputs_obj = {
            "decision_key": di_input.decision_key,
            "scope_type": di_input.scope_type,
            "scope_id": int(di_input.scope_id),
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "context": di_input.context or {},
            "engine_key": ENGINE_KEY,
            "engine_id": ENGINE_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "selector_version": SELECTOR_VERSION,
            "evaluator_version": evaluator_version,
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
        if isinstance(drift_context, dict) and drift_context:
            inputs_obj["drift_context"] = drift_context
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
            integrity["decision_output_hash"] = compute_decision_output_hash(inputs_obj=inputs_obj, outputs_obj=out)
            integrity["decision_output_hash_v2"] = compute_decision_output_hash_v2(
                inputs_obj=inputs_obj,
                outputs_obj=out,
            )
            prov["integrity"] = integrity

        return {"rules_version": rules_version, "inputs_obj": inputs_obj, "output": out, "evidence_ids": evidence_ids}

    if template_entry is None:
        out = _unsupported_template_output(
            di_input=di_input,
            pol=pol,
            reason=template_error or "unknown_template",
            evaluator_version=evaluator_version,
        )
        inputs_obj = {
            "decision_key": di_input.decision_key,
            "scope_type": di_input.scope_type,
            "scope_id": int(di_input.scope_id),
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "context": di_input.context or {},
            "engine_key": ENGINE_KEY,
            "engine_id": ENGINE_ID,
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "selector_version": SELECTOR_VERSION,
            "evaluator_version": evaluator_version,
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
            "policy_path": str(policy_path) if policy_path is not None else "",
        }
        if isinstance(drift_context, dict) and drift_context:
            inputs_obj["drift_context"] = drift_context
        evidence_ids: list[int] = []

        prov = out.get("provenance")
        if isinstance(prov, dict):
            integrity = {"evidence_fingerprint": compute_evidence_fingerprint(used_by_metric={})}
            integrity["snapshot_content_hash"] = compute_snapshot_content_hash(
                inputs_obj=inputs_obj,
                outputs_obj=out,
                evidence_ids=evidence_ids,
            )
            integrity["decision_output_hash"] = compute_decision_output_hash(inputs_obj=inputs_obj, outputs_obj=out)
            integrity["decision_output_hash_v2"] = compute_decision_output_hash_v2(
                inputs_obj=inputs_obj,
                outputs_obj=out,
            )
            prov["integrity"] = integrity

        return {"rules_version": rules_version, "inputs_obj": inputs_obj, "output": out, "evidence_ids": evidence_ids}

    if di_input.scope_type == "batch":
        scope_batch_id = int(di_input.scope_id)
        sel = select_batch_measurements(
            db,
            batch_id=scope_batch_id,
            as_of_ts=di_input.as_of_ts,
            qc_mode=di_input.qc_mode,
            metric_alias_map=(pol.policy_body.get("metric_alias_map") or {}),
            policy_qc=(pol.policy_body.get("qc_modes") or {}),
        )

        used_by_metric = sel["used_by_metric"]
        ignored = sel["ignored"]
        warnings = sel["warnings"]
        selection_provenance = sel.get("selection_provenance") or {}
    elif di_input.scope_type == "molecule":
        molecule_id = int(di_input.scope_id)
        batch_rows = _select_batches_for_molecule(db, molecule_id=molecule_id)
        batch_ids_all = [int(r["batch_id"]) for r in batch_rows]
        # Aggregation priority: newest-first (created_at DESC, id DESC).
        batch_ids_ordered = list(reversed(batch_ids_all))
        batch_created_at = {int(r["batch_id"]): _format_ts(r.get("created_at")) for r in batch_rows}

        used_by_metric: Dict[str, Any] = {}
        ignored: list[Any] = []
        warnings: list[Dict[str, Any]] = []
        metric_source_batch: Dict[str, int] = {}
        duplicate_metrics: Dict[str, list[int]] = {}
        batch_summaries: list[Dict[str, Any]] = []

        for bid in batch_ids_ordered:
            sel = select_batch_measurements(
                db,
                batch_id=int(bid),
                as_of_ts=di_input.as_of_ts,
                qc_mode=di_input.qc_mode,
                metric_alias_map=(pol.policy_body.get("metric_alias_map") or {}),
                policy_qc=(pol.policy_body.get("qc_modes") or {}),
            )

            per_used = sel["used_by_metric"]
            for mk in sorted([str(k) for k in per_used.keys()]):
                if mk not in used_by_metric:
                    used_by_metric[mk] = per_used[mk]
                    metric_source_batch[mk] = int(bid)
                else:
                    duplicate_metrics.setdefault(mk, []).append(int(bid))

            ignored.extend(sel["ignored"])
            warnings.extend(sel["warnings"])
            batch_summaries.append(
                {
                    "batch_id": int(bid),
                    "used_metric_count": int(len(per_used)),
                    "ignored_count": int(len(sel["ignored"])),
                    "warning_count": int(len(sel["warnings"])),
                }
            )

        ignored = _sort_ignored_entries(ignored)
        warnings = _sort_warning_entries(warnings)

        selection_provenance = {
            "scope_type": "molecule",
            "molecule_id": int(molecule_id),
            "batch_ids_all": batch_ids_all,
            "batch_ids_ordered": batch_ids_ordered,
            "batch_created_at": {str(k): batch_created_at.get(k) for k in sorted(list(batch_created_at.keys()))},
            "batch_selection_rule": "include all batches for molecule_id; order by created_at asc, id asc",
            "aggregation_rule": "per metric_key, select first evidence from newest batch (created_at desc, id desc)",
            "metric_source_batch_ids": {
                str(k): int(metric_source_batch[k]) for k in sorted([str(k) for k in metric_source_batch.keys()])
            },
            "duplicate_metrics": {str(k): sorted(list(set(v))) for k, v in duplicate_metrics.items()},
            "batch_summaries": batch_summaries,
        }
    else:
        raise ValueError(f"Unknown DI scope_type: {di_input.scope_type}")

    # Catalog reference + hash (catalog JSON is NOT embedded in snapshots).
    cat_ref = pol.experiment_catalog_ref
    catalog_id = str(cat_ref.get("catalog_id") or "")
    catalog_version = str(cat_ref.get("catalog_version") or "")
    catalog_hash = ""
    if catalog_id and catalog_version:
        cat = load_experiment_catalog_v0_1()
        if cat.catalog_id != catalog_id or cat.catalog_version != catalog_version:
            raise ValueError(
                f"Experiment catalog ref mismatch: policy_ref={catalog_id}:{catalog_version} file={cat.catalog_id}:{cat.catalog_version}"
            )
        catalog_hash = cat.catalog_hash


    inputs_obj = {
        "decision_key": di_input.decision_key,
        "scope_type": di_input.scope_type,
        "scope_id": int(di_input.scope_id),
        "as_of_ts": di_input.as_of_ts,
        "qc_mode": di_input.qc_mode,
        "context": di_input.context or {},
        "engine_key": ENGINE_KEY,
        "engine_id": ENGINE_ID,
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "selector_version": SELECTOR_VERSION,
        "evaluator_version": evaluator_version,
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
    if isinstance(drift_context, dict) and drift_context:
        inputs_obj["drift_context"] = drift_context

    out = _compute_di_from_used_by_metric(
        db,
        di_in=di_input,
        pol=pol,
        used_by_metric=used_by_metric,
        inputs_obj=inputs_obj,
        ignored=ignored,
        warnings=warnings,
        selection_provenance=selection_provenance,
    )

    evidence_ids = sorted([ev.measurement_id for ev in used_by_metric.values()])

    return {"rules_version": rules_version, "inputs_obj": inputs_obj, "output": out, "evidence_ids": evidence_ids}
