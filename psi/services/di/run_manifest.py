from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import DIRun, DIRunSubject, DecisionSnapshot
from psi.core.utils import now_utc, stable_json_dumps


def create_di_run_manifest(
    db: Session,
    *,
    run_id: str,
    decision_key: str,
    as_of: str,
    policy_pins: dict[str, Any] | None,
    policy_semantics_hash: str | None,
    policy_package_hash: str | None,
    scope_root_id: int,
    program_id: int | None,
    subjects: list[dict[str, Any]],
    producer_id: str = "di.rules",
    producer_version: str = "v1",
    catalog_ref: dict[str, Any] | None = None,
    notes: str | None = None,
    is_active: int = 1,
) -> DIRun:
    """Persist a deterministic DI run + subject manifest."""

    run = DIRun(
        run_id=str(run_id),
        decision_key=str(decision_key),
        as_of=str(as_of),
        producer_id=str(producer_id or "di.rules"),
        producer_version=str(producer_version or "v1"),
        policy_pins_json=stable_json_dumps(policy_pins or {}),
        policy_semantics_hash=(str(policy_semantics_hash) if policy_semantics_hash else None),
        policy_package_hash=(str(policy_package_hash) if policy_package_hash else None),
        catalog_ref_json=(stable_json_dumps(catalog_ref) if isinstance(catalog_ref, dict) else None),
        scope_root_type="molecule",
        scope_root_id=int(scope_root_id),
        program_id=(int(program_id) if program_id is not None else None),
        notes=(str(notes) if notes is not None else None),
        is_active=(1 if int(is_active or 0) else 0),
        created_at=now_utc(),
    )
    db.add(run)
    db.flush()

    ordered_subjects = sorted(
        [
            {
                "subject_index": int(s.get("subject_index", 0)),
                "scope_type": str(s.get("scope_type") or ""),
                "scope_id": int(s.get("scope_id", 0)),
                "molecule_id": (int(s["molecule_id"]) if s.get("molecule_id") is not None else None),
                "batch_id": (int(s["batch_id"]) if s.get("batch_id") is not None else None),
                "decision_snapshot_id": (
                    int(s["decision_snapshot_id"]) if s.get("decision_snapshot_id") is not None else None
                ),
            }
            for s in (subjects or [])
        ],
        key=lambda s: int(s["subject_index"]),
    )
    for s in ordered_subjects:
        db.add(
            DIRunSubject(
                di_run_id=int(run.id),
                subject_index=int(s["subject_index"]),
                scope_type=str(s["scope_type"]),
                scope_id=int(s["scope_id"]),
                molecule_id=s["molecule_id"],
                batch_id=s["batch_id"],
                decision_snapshot_id=s["decision_snapshot_id"],
                created_at=now_utc(),
            )
        )

    db.flush()
    return run


def list_run_subjects(db: Session, *, di_run_id: int) -> list[DIRunSubject]:
    return (
        db.query(DIRunSubject)
        .filter(DIRunSubject.di_run_id == int(di_run_id))
        .order_by(DIRunSubject.subject_index.asc(), DIRunSubject.id.asc())
        .all()
    )


def lookup_run_by_run_id(db: Session, *, run_id: str) -> DIRun | None:
    return (
        db.query(DIRun)
        .filter(DIRun.run_id == str(run_id))
        .order_by(DIRun.created_at.desc(), DIRun.id.desc())
        .first()
    )


def verify_di_run(db: Session, *, di_run_id: int) -> dict[str, Any]:
    run = db.query(DIRun).filter(DIRun.id == int(di_run_id)).first()
    if run is None:
        return {"ok": False, "errors": [f"di_run_not_found:{int(di_run_id)}"]}

    rows = list_run_subjects(db, di_run_id=int(di_run_id))
    errors: list[str] = []
    expected_indexes = list(range(len(rows)))
    actual_indexes = [int(r.subject_index) for r in rows]
    if actual_indexes != expected_indexes:
        errors.append(f"subject_index_not_contiguous:actual={actual_indexes}:expected={expected_indexes}")

    for r in rows:
        idx = int(r.subject_index)
        sid = r.decision_snapshot_id
        if sid is None:
            errors.append(f"missing_snapshot_link:index={idx}")
            continue
        snap = db.query(DecisionSnapshot).filter(DecisionSnapshot.id == int(sid)).first()
        if snap is None:
            errors.append(f"missing_snapshot_row:index={idx}:snapshot_id={int(sid)}")
            continue
        if str(snap.decision_key or "") != str(run.decision_key or ""):
            errors.append(
                f"decision_key_mismatch:index={idx}:expected={str(run.decision_key or '')}:actual={str(snap.decision_key or '')}"
            )
        if str(r.scope_type or "") == "molecule":
            if int(snap.molecule_id or 0) != int(r.scope_id):
                errors.append(
                    f"molecule_scope_mismatch:index={idx}:subject_scope_id={int(r.scope_id)}:snapshot_molecule_id={int(snap.molecule_id or 0)}"
                )
        elif str(r.scope_type or "") == "batch":
            if int(snap.batch_id or 0) != int(r.scope_id):
                errors.append(
                    f"batch_scope_mismatch:index={idx}:subject_scope_id={int(r.scope_id)}:snapshot_batch_id={int(snap.batch_id or 0)}"
                )
        else:
            errors.append(f"unsupported_scope_type:index={idx}:scope_type={str(r.scope_type or '')}")

    return {"ok": (len(errors) == 0), "errors": sorted(errors)}
