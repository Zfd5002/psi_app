from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.di.policy import load_policy
from psi.core.di.schema import DIInput
from psi.core.models import DecisionSnapshot, Program
from psi.core.utils import json_dumps_compact, now_utc
from psi.services.di.selectors import select_batch_measurements
from psi.services.di.templates.advance_to_in_vivo import evaluate as eval_advance_to_in_vivo


def _stable_json(obj: Any) -> str:
    # Deterministic snapshot serialization for identical inputs/DB state.
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _parse_asof_to_utc_naive(as_of_ts: Optional[str]) -> Optional[_dt.datetime]:
    if not as_of_ts:
        return None
    t = as_of_ts.strip()
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


def run_di(db: Session, *, di_input: DIInput, policy_path: Path) -> Dict[str, Any]:
    pol = load_policy(policy_path)
    if pol.decision_key != di_input.decision_key:
        raise ValueError(f"Policy decision_key mismatch: policy={pol.decision_key} input={di_input.decision_key}")

    if di_input.scope_type != "batch":
        raise ValueError("DI v0.1 supports scope_type=batch only")

    if di_input.decision_key != "advance_to_in_vivo":
        raise ValueError("DI v0.1 supports decision_key=advance_to_in_vivo only")

    # Resolve program_id + molecule_id for snapshot lineage
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
        {"bid": int(di_input.scope_id)},
    ).mappings().first()
    if not row:
        raise KeyError(f"Batch not found: {di_input.scope_id}")

    molecule_id = int(row["molecule_id"]) if row.get("molecule_id") is not None else None
    program_id = int(row["program_id"]) if row.get("program_id") is not None else None
    if program_id is None:
        p = db.query(Program).filter(Program.name == "PSI_EXAMPLES").first()
        program_id = int(p.id) if p else 1

    sel = select_batch_measurements(
        db,
        batch_id=int(di_input.scope_id),
        as_of_ts=di_input.as_of_ts,
        qc_mode=di_input.qc_mode,
        metric_alias_map=(pol.policy.get("metric_alias_map") or {}),
        policy_qc=(pol.policy.get("qc_modes") or {}),
    )

    used_by_metric = sel["used_by_metric"]
    ignored = sel["ignored"]
    warnings = sel["warnings"]

    templ = eval_advance_to_in_vivo(
        used_by_metric=used_by_metric,
        policy=pol.policy,
        context=di_input.context or {},
    )

    # strict-mode cannot_assess heuristic: nothing usable and strict QC blocked candidates
    strict_blocked = (
        (di_input.qc_mode == "strict")
        and (len(used_by_metric) == 0)
        and any(ig.reason in ("qc_unreviewed_strict", "qc_unknown_strict", "qc_rejected") for ig in ignored)
    )

    decision_state = templ["decision_state"]
    if strict_blocked:
        decision_state = "cannot_assess"
        templ["blockers"].insert(0, {"blocker_key": "unreviewed_qc_required_metric", "detail": {"qc_mode": "strict", "note": "No acceptable evidence under strict QC."}})

    out = {
        "decision_state": decision_state,
        "policy": {"name": pol.name, "version": pol.version, "hash": pol.hash},
        "provenance": {
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "selection_semantics": {
                "ignore_for_model": "always_ignored",
                "outliers": "not_dropped_in_v0_1",
                "primary": "is_primary_first_else_newest_timestamp",
            },
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
        },
        "gates": [g.__dict__ for g in templ["gates"]],
        "blockers": templ["blockers"],
        "risk_flags": templ["risk_flags"],
    }

    rules_version = f"{pol.name}:{pol.version}:{pol.hash[:12]}"
    inputs_json = _stable_json(
        {
            "decision_key": di_input.decision_key,
            "scope_type": di_input.scope_type,
            "scope_id": di_input.scope_id,
            "as_of_ts": di_input.as_of_ts,
            "qc_mode": di_input.qc_mode,
            "context": di_input.context or {},
            "policy_path": str(policy_path),
        }
    )
    outputs_json = _stable_json(out)
    evidence_ids_json = _stable_json(sorted([ev.measurement_id for ev in used_by_metric.values()]))

    snap = DecisionSnapshot(
        program_id=int(program_id),
        molecule_id=molecule_id,
        batch_id=int(di_input.scope_id),
        decision_key=di_input.decision_key,
        rules_version=rules_version,
        inputs_json=inputs_json,
        outputs_json=outputs_json,
        evidence_ids_json=evidence_ids_json,
        as_of_ts=_parse_asof_to_utc_naive(di_input.as_of_ts),
        created_at=now_utc(),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)

    return {"snapshot_id": snap.id, "output": out}
