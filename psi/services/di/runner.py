from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from psi.core.di.catalog import load_experiment_catalog_v0_1
from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput
from psi.core.models import DIRunSubject, DecisionSnapshot, Molecule, Program
from psi.core.utils import now_utc, stable_json_dumps
from psi.services.di.run_manifest import create_di_run_manifest
from psi.services.di.selection import select_batch_measurements
from psi.services.di.compute import _compute_di_from_used_by_metric
from psi.services.di.error_output import build_di_error_output_payload
from psi.services.di.integrity import compute_decision_output_hash, compute_decision_output_hash_v2, compute_evidence_fingerprint, compute_snapshot_content_hash
from psi.services.di.templates.registry import resolve_template_entry
from psi.services.di.util import value_functions_enforcement_reason
from psi.services.dev_board import invalidate_program_board_cache
from psi.version import PSI_VERSION


# DI snapshot contract identifiers (stable, explicit, portable)
ENGINE_KEY = "di"
ENGINE_ID = "di.engine.v0_1"
SNAPSHOT_SCHEMA_VERSION = "di.snapshot.v0_1"
SELECTOR_VERSION = "di.selector.v0_1"

# explicit selection semantics version (constitution-locked)
DI_SELECTION_SEMANTICS_VERSION = "di.selection.v0_1"
OUTPUT_EXTENSION_FLAGS = ["value_functions_enforced_v0_1", "error_output_parity_v2_0a"]

# Policy package schema allowlist (governance guardrail)
ALLOWED_POLICY_SCHEMA_VERSIONS = {"di.policy_package.v0_1"}
logger = logging.getLogger(__name__)


def _sha256_of_stable_json(obj: Any) -> str:
    s = stable_json_dumps(obj)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _has_output_extension(inputs_obj: Dict[str, Any], flag: str) -> bool:
    vals = inputs_obj.get("output_extensions") if isinstance(inputs_obj, dict) else []
    if not isinstance(vals, list):
        return False
    return str(flag) in [str(x) for x in vals]


def _policy_supports_v0_4_extensions(pol: Any) -> bool:
    try:
        v = str(getattr(pol, "version", "") or "").strip().lower()
    except Exception:
        v = ""
    return v.startswith("v0.4")


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


def _build_di_inputs_obj(
    *,
    di_input: DIInput,
    pol: Any,
    evaluator_version: str,
    template_key: str,
    template_name: str,
    catalog_id: str,
    catalog_version: str,
    catalog_hash: str,
    policy_path: Optional[Path],
    drift_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the authoritative DI snapshot inputs payload.

    Centralized to keep success and deterministic error paths schema-aligned.
    """

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
        "output_extensions": list(OUTPUT_EXTENSION_FLAGS),
        "template_key": str(template_key or ""),
        "template_name": str(template_name or template_key or ""),
        "policy_id": pol.policy_id,
        "policy_version": pol.version,
        "policy_name": pol.name,
        "policy_semantics_hash": pol.policy_semantics_hash,
        "policy_package_hash": pol.policy_package_hash,
        "policy_schema_version": pol.schema_version,
        "policy_hash": pol.policy_semantics_hash,
        "policy_source": pol.source_name,
        "policy_json_canonical": pol.policy_body_canonical_json,
        "catalog_id": str(catalog_id or ""),
        "catalog_version": str(catalog_version or ""),
        "catalog_hash": str(catalog_hash or ""),
        # Non-authoritative, machine-local metadata (debugging only)
        "policy_path": str(policy_path) if policy_path is not None else "",
    }
    if isinstance(drift_context, dict) and drift_context:
        inputs_obj["drift_context"] = drift_context
    return inputs_obj


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
    return build_di_error_output_payload(
        di_input=di_input,
        pol=pol,
        evaluator_version=evaluator_version,
        warning_kind=warning_kind,
        warning_detail=warning_detail,
        blocker_key=blocker_key,
        blocker_detail=blocker_detail,
        risk_flag=risk_flag,
        risk_note=risk_note,
        risk_enriched_key=risk_enriched_key,
        risk_enriched_explanation=risk_enriched_explanation,
        readiness_blocker_key=readiness_blocker_key,
        readiness_blocker_explanation=readiness_blocker_explanation,
        readiness_blocking_reason=readiness_blocking_reason,
        engine_id=ENGINE_ID,
        snapshot_schema_version=SNAPSHOT_SCHEMA_VERSION,
        selector_version=SELECTOR_VERSION,
        selection_semantics_version=DI_SELECTION_SEMANTICS_VERSION,
        code_version=PSI_VERSION,
        stable_hash_json_fn=_sha256_of_stable_json,
    )


def _complete_di_error_output_contract_parity(
    *,
    out: Dict[str, Any],
    di_input: DIInput,
    pol: Any,
    inputs_obj: Dict[str, Any],
) -> Dict[str, Any]:
    """Additive, replay-safe error-output parity completion for new snapshots only.

    Historical snapshots replay using stored inputs_obj without the parity extension flag,
    so this helper becomes a no-op and preserves old replay surfaces.
    """
    template_flag_enabled = False
    expected_eval_version = ""
    try:
        template_entry = resolve_template_entry(
            decision_key=str(di_input.decision_key or ""),
            template_key=str(getattr(pol, "template_key", "") or ""),
        )
        template_flag_enabled = bool((template_entry or {}).get("enforce_value_functions"))
        expected_eval_version = str((template_entry or {}).get("evaluator_version") or "")
        applicable_value_fn = True
    except Exception:
        applicable_value_fn = False
    engine_obj = out.get("engine") if isinstance(out, dict) else {}
    if not isinstance(engine_obj, dict):
        engine_obj = {}
    evaluator_version_actual = str(
        (inputs_obj or {}).get("evaluator_version")
        or engine_obj.get("evaluator_version")
        or ""
    )
    value_fn_reason = value_functions_enforcement_reason(
        applicable=applicable_value_fn,
        policy_flag_enabled=template_flag_enabled,
        evaluator_version_expected=expected_eval_version,
        evaluator_version_actual=evaluator_version_actual,
    )

    if not _has_output_extension(inputs_obj, "error_output_parity_v2_0a"):
        if _has_output_extension(inputs_obj, "value_functions_enforced_v0_1"):
            out["value_functions_enforced"] = False
            out.setdefault("value_functions_enforcement_reason", str(value_fn_reason))
        return out

    out.setdefault("metric_evaluations", {})
    out.setdefault("recommended_experiments", [])
    out.setdefault("comparability", {
        "metric_level": [],
        "qc_coherence": [],
        "summary": {"total_flags": 0, "high_severity_count": 0},
        "is_comparable": False,
        "reason": "error_output",
        "policy_semantics_hash_changed": False,
        "evidence_fingerprint_changed": False,
    })
    out.setdefault("confidence_degradation", {"triggered": False, "reasons": []})
    out.setdefault("why_evidence", {})
    out.setdefault("drift_type", "NO_CHANGE")
    out.setdefault("state_transition", None)
    out.setdefault("shortlisting", None)
    out.setdefault("scope_semantics", None)
    out.setdefault("context_evaluation", None)
    out.setdefault("template_dependency_graph", None)
    if _has_output_extension(inputs_obj, "value_functions_enforced_v0_1"):
        out.setdefault("value_functions_enforced", False)
        out.setdefault("value_functions_enforcement_reason", str(value_fn_reason))
    if not _policy_supports_v0_4_extensions(pol):
        # Keep v0.3 surfaces aligned for new v0.3 snapshots too: the parity helper is enabled
        # for all new snapshots, but v0.4-only extension surfaces remain gated by policy version.
        out.pop("scope_semantics", None)
        out.pop("context_evaluation", None)
        out.pop("template_dependency_graph", None)
    return out


def _attach_integrity_hashes(
    *,
    out: Dict[str, Any],
    inputs_obj: Dict[str, Any],
    evidence_ids: list[int],
    used_by_metric: Dict[str, Any],
) -> None:
    prov = out.get("provenance")
    if not isinstance(prov, dict):
        return
    integrity = {"evidence_fingerprint": compute_evidence_fingerprint(used_by_metric=used_by_metric)}
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
        logger.warning("invalid PSI_DI_BASELINE_CUTOFF_ISO ignored: %s", cutoff_raw)

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


def _select_batches_for_multi_subject_run(db: Session, *, molecule_id: int) -> list[Dict[str, Any]]:
    """Deterministic batch order for multi-subject runs.

    Rule:
    - include all batches where batch.molecule_id == molecule_id
    - order by created_at DESC, then id DESC (stable, tie-safe)
    """

    rows = (
        db.execute(
            text(
                """
                SELECT id, created_at
                FROM batches
                WHERE molecule_id = :mid
                ORDER BY created_at DESC, id DESC
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


def _build_di_run_id(
    *,
    molecule_id: int,
    decision_key: str,
    as_of: str,
    created_at_iso: str,
    subject_scope_ids: list[int],
) -> str:
    payload = {
        "molecule_id": int(molecule_id),
        "decision_key": str(decision_key),
        "as_of": str(as_of),
        "created_at": str(created_at_iso),
        "subject_scope_ids": [int(x) for x in subject_scope_ids],
    }
    digest = hashlib.sha256(stable_json_dumps(payload).encode("utf-8")).hexdigest()
    return f"di_run_{digest[:24]}"


def run_di_multi_subject(
    db: Session,
    *,
    molecule_id: int,
    decision_key: str,
    as_of_ts: str | None,
    policy_path: Path,
    qc_mode: str = "model_safe",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run DI deterministically for molecule scope plus all batch subjects.

    The run links immutable DecisionSnapshot rows to a run-manifest envelope in
    di_runs/di_run_subjects and does not alter snapshot semantics.
    """

    molecule_id_int = int(molecule_id)
    program_id = _resolve_molecule_lineage(db, molecule_id=molecule_id_int)
    as_of_value = str(as_of_ts or "")
    created_at_dt = now_utc()
    created_at_iso = created_at_dt.isoformat()
    pol = load_policy(policy_path)
    policy_pins = {
        "policy_id": str(getattr(pol, "policy_id", "") or ""),
        "policy_version": str(getattr(pol, "version", "") or ""),
        "policy_source": str(getattr(pol, "source_name", "") or ""),
    }

    subjects: list[dict[str, Any]] = [
        {
            "subject_index": 0,
            "scope_type": "molecule",
            "scope_id": molecule_id_int,
            "molecule_id": molecule_id_int,
            "batch_id": None,
        }
    ]
    for i, b in enumerate(_select_batches_for_multi_subject_run(db, molecule_id=molecule_id_int), start=1):
        subjects.append(
            {
                "subject_index": int(i),
                "scope_type": "batch",
                "scope_id": int(b["batch_id"]),
                "molecule_id": molecule_id_int,
                "batch_id": int(b["batch_id"]),
            }
        )

    run_id = _build_di_run_id(
        molecule_id=molecule_id_int,
        decision_key=str(decision_key),
        as_of=as_of_value,
        created_at_iso=created_at_iso,
        subject_scope_ids=[int(s["scope_id"]) for s in subjects],
    )
    run = create_di_run_manifest(
        db,
        run_id=run_id,
        decision_key=str(decision_key),
        as_of=as_of_value,
        policy_pins=policy_pins,
        policy_semantics_hash=str(getattr(pol, "policy_semantics_hash", "") or ""),
        policy_package_hash=str(getattr(pol, "policy_package_hash", "") or ""),
        scope_root_id=molecule_id_int,
        program_id=int(program_id),
        subjects=subjects,
        producer_id="di.rules",
        producer_version="v1",
        catalog_ref=None,
        notes=None,
        is_active=1,
    )
    db.commit()
    db.refresh(run)

    snapshot_ids: list[int] = []
    ordered_subjects = sorted(subjects, key=lambda s: int(s["subject_index"]))
    for s in ordered_subjects:
        di_input = DIInput(
            decision_key=str(decision_key),
            scope_type=str(s["scope_type"]),
            scope_id=int(s["scope_id"]),
            qc_mode=str(qc_mode or "model_safe"),
            as_of_ts=(as_of_value if as_of_value else None),
            context=(dict(context) if isinstance(context, dict) else {}),
        )
        run_res = run_di(db, di_input=di_input, policy_path=policy_path)
        snapshot_id = int(run_res.get("snapshot_id"))
        snapshot_ids.append(snapshot_id)
        row = (
            db.query(DIRunSubject)
            .filter(DIRunSubject.di_run_id == int(run.id))
            .filter(DIRunSubject.subject_index == int(s["subject_index"]))
            .first()
        )
        if row is None:
            raise RuntimeError(f"Missing di_run_subject row for di_run_id={int(run.id)} index={int(s['subject_index'])}")
        row.decision_snapshot_id = int(snapshot_id)
        db.commit()

    return {"di_run_id": int(run.id), "run_id": str(run.run_id), "snapshot_ids": list(snapshot_ids)}


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


def _reconcile_single_active_snapshot_for_scope(
    db: Session,
    *,
    decision_key: str,
    program_id: int,
    molecule_id: Optional[int],
    batch_id: Optional[int],
    new_snapshot_id: int,
) -> None:
    """Enforce single active snapshot (authoritative = superseded_by_snapshot_id IS NULL).

    This runs in the same transaction as the insert. If a concurrent writer created an
    additional active snapshot after our preflight query, we deterministically supersede
    any older active rows to the newly inserted snapshot before commit.
    """
    extra_active_ids = [
        int(r[0])
        for r in db.execute(
            text(
                """
                SELECT id
                FROM decision_snapshots
                WHERE decision_key = :dk
                  AND program_id = :pid
                  AND COALESCE(molecule_id, 0) = COALESCE(:mid, 0)
                  AND COALESCE(batch_id, 0) = COALESCE(:bid, 0)
                  AND superseded_by_snapshot_id IS NULL
                  AND id <> :new_id
                """
            ),
            {
                "dk": str(decision_key),
                "pid": int(program_id),
                "mid": molecule_id,
                "bid": (int(batch_id) if batch_id is not None else None),
                "new_id": int(new_snapshot_id),
            },
        ).fetchall()
    ]
    if extra_active_ids:
        q = text(
            """
            UPDATE decision_snapshots
            SET is_superseded = 1,
                superseded_at = CURRENT_TIMESTAMP,
                superseded_by_snapshot_id = :new_id
            WHERE id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        db.execute(q, {"new_id": int(new_snapshot_id), "ids": list(extra_active_ids)})

    active_count = int(
        db.execute(
            text(
                """
                SELECT COUNT(1)
                FROM decision_snapshots
                WHERE decision_key = :dk
                  AND program_id = :pid
                  AND COALESCE(molecule_id, 0) = COALESCE(:mid, 0)
                  AND COALESCE(batch_id, 0) = COALESCE(:bid, 0)
                  AND superseded_by_snapshot_id IS NULL
                """
            ),
            {
                "dk": str(decision_key),
                "pid": int(program_id),
                "mid": molecule_id,
                "bid": (int(batch_id) if batch_id is not None else None),
            },
        ).scalar()
        or 0
    )
    if active_count != 1:
        raise RuntimeError(
            "DecisionSnapshot supersession integrity violation: "
            f"expected exactly one active snapshot for scope, found {active_count}"
        )


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



    # v1.2.9q+: intentional two-pass supersession (no behavior change):
    # 1) mark prior ACTIVE rows superseded before inserting the new snapshot so the
    #    partial unique ACTIVE index can never reject the insert;
    # 2) after the new row has an id, backfill superseded_by_snapshot_id to point at it.
    # A final reconcile step remains as the concurrency guardrail if another writer raced us.
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

    try:
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

        _reconcile_single_active_snapshot_for_scope(
            db,
            decision_key=di_input.decision_key,
            program_id=int(program_id),
            molecule_id=molecule_id,
            batch_id=(int(batch_id) if batch_id is not None else None),
            new_snapshot_id=int(snap.id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(snap)
    invalidate_program_board_cache(program_id=int(program_id))

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
    template_key = str(getattr(pol, "template_key", "") or "")
    template_name = template_key

    # Policy governance guardrail: enforce known package schema versions.
    if str(pol.schema_version) not in ALLOWED_POLICY_SCHEMA_VERSIONS:
        out = _policy_schema_mismatch_output(
            di_input=di_input,
            pol=pol,
            mismatch="unknown_policy_schema_version",
            evaluator_version=evaluator_version,
        )
        inputs_obj = _build_di_inputs_obj(
            di_input=di_input,
            pol=pol,
            evaluator_version=evaluator_version,
            template_key=template_key,
            template_name=template_name,
            catalog_id="",
            catalog_version="",
            catalog_hash="",
            policy_path=policy_path,
            drift_context=drift_context,
        )
        evidence_ids: list[int] = []
        out = _complete_di_error_output_contract_parity(
            out=out,
            di_input=di_input,
            pol=pol,
            inputs_obj=inputs_obj,
        )

        # v1.2.9k integrity
        _attach_integrity_hashes(out=out, inputs_obj=inputs_obj, evidence_ids=evidence_ids, used_by_metric={})

        return {"rules_version": rules_version, "inputs_obj": inputs_obj, "output": out, "evidence_ids": evidence_ids}

    if template_entry is None:
        out = _unsupported_template_output(
            di_input=di_input,
            pol=pol,
            reason=template_error or "unknown_template",
            evaluator_version=evaluator_version,
        )
        inputs_obj = _build_di_inputs_obj(
            di_input=di_input,
            pol=pol,
            evaluator_version=evaluator_version,
            template_key=template_key,
            template_name=template_name,
            catalog_id="",
            catalog_version="",
            catalog_hash="",
            policy_path=policy_path,
            drift_context=drift_context,
        )
        evidence_ids: list[int] = []
        out = _complete_di_error_output_contract_parity(
            out=out,
            di_input=di_input,
            pol=pol,
            inputs_obj=inputs_obj,
        )

        _attach_integrity_hashes(out=out, inputs_obj=inputs_obj, evidence_ids=evidence_ids, used_by_metric={})

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


    inputs_obj = _build_di_inputs_obj(
        di_input=di_input,
        pol=pol,
        evaluator_version=evaluator_version,
        template_key=template_key,
        template_name=template_name,
        catalog_id=catalog_id,
        catalog_version=catalog_version,
        catalog_hash=catalog_hash,
        policy_path=policy_path,
        drift_context=drift_context,
    )

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
