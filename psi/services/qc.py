from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.models import MeasurementQC, MeasurementQCEvent
from psi.core.utils import now_utc


VALID_ACTIONS = {"approve", "reject", "quarantine", "clear", "note"}
VALID_STATUSES = {"approved", "rejected", "quarantined", "unreviewed"}
VALID_POLICIES = {"include", "exclude_soft", "exclude_hard", "quarantine"}


def _now_utc() -> datetime:
    return now_utc()


def get_qc_state_for_measurements(db: Session, measurement_ids: Iterable[int]) -> Dict[int, Dict[str, Any]]:
    mids = [int(x) for x in measurement_ids if x is not None]
    if not mids:
        return {}

    rows = (
        db.query(MeasurementQC)
        .filter(MeasurementQC.measurement_id.in_(mids))
        .all()
    )
    out: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        out[int(r.measurement_id)] = {
            "status": r.status or "unreviewed",
            "ignore_policy": r.ignore_policy or "include",
            "ignore_reason_code": r.ignore_reason_code,
            "ignore_note": r.ignore_note,
            "updated_at": r.updated_at,
            "last_event_id": r.last_event_id,
        }
    return out


def _status_for_action(action: str) -> str:
    if action == "approve":
        return "approved"
    if action == "reject":
        return "rejected"
    if action == "quarantine":
        return "quarantined"
    if action == "clear":
        return "unreviewed"
    # note: handled by caller (keep current)
    return "unreviewed"


def append_qc_event(
    db: Session,
    *,
    measurement_id: int,
    record_id: Optional[int],
    metric_key: Optional[str],
    action: str,
    actor: str,
    note: str | None = None,
    ignore_policy: str | None = None,
    ignore_reason_code: str | None = None,
    ignore_note: str | None = None,
    clear_legacy_ignore: bool = False,
) -> MeasurementQCEvent:
    """Append a QC event and refresh the latest-state cache.

    Governance is in MeasurementQCEvent (append-only). MeasurementQC is derived cache.
    """
    action_n = (action or "").strip().lower()
    if action_n not in VALID_ACTIONS:
        raise ValueError(f"Invalid action: {action}")

    actor_n = (actor or "").strip()
    if not actor_n:
        raise ValueError("actor is required")

    pol = (ignore_policy or "").strip().lower() if ignore_policy is not None else None
    if pol == "":
        pol = None
    if pol is not None and pol not in VALID_POLICIES:
        raise ValueError(f"Invalid ignore_policy: {ignore_policy}")

    # Load current cache for note-only events
    current = (
        db.query(MeasurementQC)
        .filter(MeasurementQC.measurement_id == int(measurement_id))
        .one_or_none()
    )
    if action_n == "note":
        status_after = (current.status if current and current.status else "unreviewed")
    else:
        status_after = _status_for_action(action_n)

    if status_after not in VALID_STATUSES:
        status_after = "unreviewed"

    ev = MeasurementQCEvent(
        measurement_id=int(measurement_id),
        record_id=int(record_id) if record_id is not None else None,
        metric_key=(metric_key or None),
        action=action_n,
        status_after=status_after,
        actor=actor_n,
        note=(note or None),
        ignore_policy=pol,
        ignore_reason_code=(ignore_reason_code or None),
        ignore_note=(ignore_note or None),
        created_at=_now_utc(),
    )
    db.add(ev)
    db.flush()  # assign ev.id

    # Refresh latest-state cache
    if current is None:
        current = MeasurementQC(
            measurement_id=int(measurement_id),
            record_id=int(record_id) if record_id is not None else None,
            metric_key=(metric_key or None),
            status="unreviewed",
            ignore_policy="include",
            updated_at=_now_utc(),
        )
        db.add(current)

    # Apply state transitions
    current.status = status_after
    if pol is not None:
        current.ignore_policy = pol
    if ignore_reason_code is not None:
        current.ignore_reason_code = (ignore_reason_code or None)
    if ignore_note is not None:
        current.ignore_note = (ignore_note or None)
    current.last_event_id = int(ev.id)
    current.updated_at = _now_utc()

    # Bridge to legacy ignore_for_model to preserve model safety.
    # We only auto-set ignore_for_model when exclusion is selected.
    # Clearing legacy ignore is explicit (checkbox).
    if pol in ("exclude_soft", "exclude_hard", "quarantine"):
        db.execute(
            text("UPDATE data_measurements SET ignore_for_model = 1 WHERE id = :mid"),
            {"mid": int(measurement_id)},
        )
    elif clear_legacy_ignore and pol == "include":
        db.execute(
            text("UPDATE data_measurements SET ignore_for_model = 0 WHERE id = :mid"),
            {"mid": int(measurement_id)},
        )

    return ev


def get_qc_counts_for_batches(db: Session, *, molecule_id: int) -> Dict[int, Dict[str, int]]:
    """Return per-batch QC counts for measurements under a molecule.

    Counts are per measurement row (data_measurements), grouped by DataRecord.batch_id.
    """
    q = text(
        """
        SELECT
          dr.batch_id AS batch_id,
          COUNT(dm.id) AS total,
          SUM(CASE WHEN COALESCE(qc.status, 'unreviewed') = 'approved' THEN 1 ELSE 0 END) AS approved,
          SUM(CASE WHEN COALESCE(qc.status, 'unreviewed') = 'rejected' THEN 1 ELSE 0 END) AS rejected,
          SUM(CASE WHEN COALESCE(qc.status, 'unreviewed') = 'quarantined' THEN 1 ELSE 0 END) AS quarantined,
          SUM(CASE WHEN COALESCE(qc.status, 'unreviewed') = 'unreviewed' THEN 1 ELSE 0 END) AS pending
        FROM data_records dr
        JOIN data_measurements dm ON dm.data_record_id = dr.id
        LEFT JOIN measurement_qc qc ON qc.measurement_id = dm.id
        WHERE dr.molecule_id = :mid AND dr.batch_id IS NOT NULL
        GROUP BY dr.batch_id
        """
    )
    rows = db.execute(q, {"mid": int(molecule_id)}).mappings().all()
    out: Dict[int, Dict[str, int]] = {}
    for r in rows:
        bid = r.get("batch_id")
        if bid is None:
            continue
        out[int(bid)] = {
            "total": int(r.get("total") or 0),
            "approved": int(r.get("approved") or 0),
            "rejected": int(r.get("rejected") or 0),
            "quarantined": int(r.get("quarantined") or 0),
            "pending": int(r.get("pending") or 0),
        }
    return out
