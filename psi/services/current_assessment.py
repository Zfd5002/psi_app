from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from psi.core.di.schema import DIInput
from psi.core.models import Batch, DecisionSnapshot, Molecule
from psi.services import development_progression as progression_svc
from psi.services.di.runner import run_di
from psi.services.di.web import latest_policy_for_decision, list_di_policies
from psi.services.insight_engine import build_insight_bundle

DEFAULT_DECISION_KEY = progression_svc.canonical_decision_key()


def _stable_default_policy_for_decision(decision_key: str) -> dict[str, Any] | None:
    dk = str(decision_key or "").strip()
    selected = latest_policy_for_decision(dk)
    options = [p for p in list_di_policies() if str(p.get("decision_key") or "") == dk]
    if dk == "advance_to_in_vivo":
        alt = next((p for p in options if str(p.get("policy_version") or "") == "v0.5"), None)
        if alt is not None:
            selected = alt
    if dk == "ready_for_scaleup_screen":
        alt = next((p for p in options if str(p.get("policy_version") or "") == "v0.2"), None)
        if alt is not None:
            selected = alt
    return selected


def infer_molecule_scope_for_record(*, db: Session, molecule_id: int | None, batch_id: int | None) -> int | None:
    if molecule_id is not None:
        return int(molecule_id)
    if batch_id is None:
        return None
    b = db.get(Batch, int(batch_id))
    if b is None:
        return None
    return int(b.molecule_id)


def latest_active_snapshot_for_molecule(
    db: Session,
    *,
    molecule_id: int,
    decision_key: str = DEFAULT_DECISION_KEY,
) -> DecisionSnapshot | None:
    return (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == int(molecule_id))
        .filter(DecisionSnapshot.decision_key == str(decision_key))
        .filter(DecisionSnapshot.superseded_by_snapshot_id.is_(None))
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .first()
    )


def _assessment_state_label(*, bundle: dict[str, Any]) -> str:
    status = str(bundle.get("molecule_status") or "").strip().lower()
    missing = [x for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)]
    if status in {"ready", "pass", "approved"}:
        return "Ready"
    if missing:
        return "Missing Data"
    if status in {"blocked", "fail", "failed", "not_ready", "hold"}:
        return "Failed Criteria"
    return "Not Evaluated"


def refresh_current_assessment_for_molecule(
    db: Session,
    *,
    molecule_id: int,
    trigger: str,
    decision_key: str = DEFAULT_DECISION_KEY,
) -> dict[str, Any]:
    mid = int(molecule_id)
    mol = db.get(Molecule, mid)
    if mol is None:
        raise KeyError("Molecule not found")

    prev = latest_active_snapshot_for_molecule(db, molecule_id=mid, decision_key=decision_key)
    selected_policy = _stable_default_policy_for_decision(decision_key)
    if not selected_policy or not str(selected_policy.get("path") or "").strip():
        raise ValueError("No DI policy path available for current assessment refresh")
    policy_path = Path(str(selected_policy["path"]))

    di_in = DIInput(
        decision_key=str(decision_key),
        scope_type="molecule",
        scope_id=mid,
        qc_mode="model_safe",
        context={
            "mode": "auto_current_assessment",
            "trigger": str(trigger or "unknown"),
        },
    )
    res = run_di(db, di_input=di_in, policy_path=policy_path)
    snap_id = int(res.get("snapshot_id"))
    out = res.get("output") if isinstance(res.get("output"), dict) else {}
    bundle = build_insight_bundle(out if out else None)
    progression = progression_svc.build_progression_summary(out)
    missing_metrics = [
        str(x.get("metric_key") or "")
        for x in (bundle.get("missing_evidence") or [])
        if isinstance(x, dict) and str(x.get("metric_key") or "").strip()
    ]
    strongest_blocking = [
        str(x.get("metric_key") or "")
        for x in (bundle.get("strongest_blocking_evidence") or [])
        if isinstance(x, dict) and str(x.get("metric_key") or "").strip()
    ]
    recs = [x for x in (bundle.get("recommended_experiments") or []) if isinstance(x, dict)]
    next_metric = str((recs[0].get("metric_key") if recs else "") or "").strip()
    return {
        "molecule_id": mid,
        "program_id": int(mol.program_id),
        "decision_key": str(decision_key),
        "snapshot_id": snap_id,
        "previous_snapshot_id": (int(prev.id) if prev is not None else None),
        "refresh_semantics": ("first_assessment" if prev is None else "updated_assessment"),
        "state_label": _assessment_state_label(bundle=bundle),
        "missing_metrics": missing_metrics,
        "strongest_blocking_metrics": strongest_blocking,
        "suggested_next_metric": next_metric,
        "current_stage_label": str(progression.get("current_stage_label") or ""),
        "blocking_stage_label": str(progression.get("blocking_stage_label") or ""),
        "passed_stage_labels": list(progression.get("passed_stage_labels") or []),
        "missing_requirement_labels": list(progression.get("missing_requirement_labels") or []),
        "failing_requirement_labels": list(progression.get("failing_requirement_labels") or []),
        "recommended_next_step": str(progression.get("recommended_next_step") or ""),
        "progression_summary": progression,
    }
