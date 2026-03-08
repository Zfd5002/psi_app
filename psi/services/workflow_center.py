from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from psi.core.models import DataRecord, Evidence, EvidenceCitation, Molecule
from psi.services import experiment_tasks as experiment_tasks_svc


def build_program_workflow_center(db: Session, *, program_id: int) -> dict[str, Any]:
    pid = int(program_id)
    tasks = experiment_tasks_svc.list_tasks_for_program(db, program_id=pid, include_done=True)
    molecules = db.query(Molecule).filter(Molecule.program_id == pid).all()
    molecule_by_id = {int(m.id): m for m in molecules}

    ready_to_start = [t for t in tasks if str(t.status or "") == "planned"]
    in_progress = [t for t in tasks if str(t.status or "") == "in_progress"]
    blocked_tasks = [t for t in tasks if str(t.status or "") == "blocked"]
    awaiting_data_entry = [t for t in in_progress if (t.linked_data_record_id is None and (t.metric_key or t.suggested_assay))]
    recently_completed = [t for t in tasks if str(t.status or "") == "done"][:20]

    source_rollup = Counter(str(getattr(t, "source_kind", "") or "manual").strip().lower() or "manual" for t in tasks)
    today = date.today()
    overdue_open = 0
    unassigned_open = 0
    for t in tasks:
        st = str(getattr(t, "status", "") or "").strip().lower()
        if st == "done":
            continue
        if not str(getattr(t, "owner_text", "") or "").strip():
            unassigned_open += 1
        raw_due = getattr(t, "due_date", None)
        if raw_due and raw_due < today:
            overdue_open += 1

    recent_data_records = (
        db.query(DataRecord)
        .filter(DataRecord.program_id == pid)
        .order_by(DataRecord.created_at.desc(), DataRecord.id.desc())
        .limit(8)
        .all()
    )
    recent_evidence = (
        db.query(Evidence)
        .filter(Evidence.program_id == pid)
        .order_by(Evidence.created_at.desc(), Evidence.id.desc())
        .limit(8)
        .all()
    )
    recent_record_ids = [int(r.id) for r in recent_data_records]
    cited_record_ids: set[int] = set()
    if recent_record_ids:
        cited_record_ids = {
            int(row[0])
            for row in db.query(EvidenceCitation.data_record_id)
            .filter(EvidenceCitation.data_record_id.in_(recent_record_ids))
            .all()
            if row and row[0] is not None
        }
    pending_interpretation = [r for r in recent_data_records if int(r.id) not in cited_record_ids]

    return {
        "ready_to_start": ready_to_start,
        "in_progress": in_progress,
        "blocked_tasks": blocked_tasks,
        "awaiting_data_entry": awaiting_data_entry,
        "recently_completed": recently_completed,
        "molecule_by_id": molecule_by_id,
        "source_rollup": dict(source_rollup),
        "overdue_open": overdue_open,
        "unassigned_open": unassigned_open,
        "recent_data_records": recent_data_records,
        "recent_evidence": recent_evidence,
        "pending_interpretation": pending_interpretation,
    }

