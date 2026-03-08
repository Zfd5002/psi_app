from __future__ import annotations

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from psi.core.models import DataRecord, ExperimentTask
from psi.core.utils import now_utc

TASK_STATUSES: tuple[str, ...] = ("planned", "in_progress", "done", "blocked")
TASK_URGENCY: tuple[str, ...] = ("critical", "high", "normal", "low")
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"in_progress", "blocked"},
    "in_progress": {"done", "blocked"},
    "blocked": {"in_progress"},
    "done": set(),
}


def _normalize_status(status: str | None) -> str:
    s = str(status or "").strip().lower()
    return s if s in TASK_STATUSES else "planned"


def _normalize_urgency(urgency: str | None) -> str:
    u = str(urgency or "").strip().lower()
    return u if u in TASK_URGENCY else "normal"


def _sort_clause():
    urgency_rank = case(
        (ExperimentTask.urgency == "critical", 0),
        (ExperimentTask.urgency == "high", 1),
        (ExperimentTask.urgency == "normal", 2),
        (ExperimentTask.urgency == "low", 3),
        else_=4,
    )
    status_rank = case(
        (ExperimentTask.status == "in_progress", 0),
        (ExperimentTask.status == "planned", 1),
        (ExperimentTask.status == "blocked", 2),
        (ExperimentTask.status == "done", 3),
        else_=4,
    )
    return (
        status_rank.asc(),
        urgency_rank.asc(),
        func.coalesce(ExperimentTask.due_date, "9999-12-31").asc(),
        ExperimentTask.created_at.asc(),
        ExperimentTask.id.asc(),
    )


def _open_sort_clause():
    urgency_rank = case(
        (ExperimentTask.urgency == "critical", 0),
        (ExperimentTask.urgency == "high", 1),
        (ExperimentTask.urgency == "normal", 2),
        (ExperimentTask.urgency == "low", 3),
        else_=4,
    )
    return (
        urgency_rank.asc(),
        func.coalesce(ExperimentTask.due_date, "9999-12-31").asc(),
        ExperimentTask.created_at.asc(),
        ExperimentTask.id.asc(),
    )


def create_experiment_task(
    db: Session,
    *,
    program_id: int,
    molecule_id: int,
    metric_key: str = "",
    suggested_assay: str = "",
    status: str = "planned",
    owner_text: str = "",
    due_date: str = "",
    urgency: str = "normal",
    source_kind: str = "manual",
    source_snapshot_id: int | None = None,
    notes: str = "",
) -> ExperimentTask:
    task = ExperimentTask(
        program_id=int(program_id),
        molecule_id=int(molecule_id),
        metric_key=(str(metric_key or "").strip() or None),
        suggested_assay=(str(suggested_assay or "").strip() or None),
        status=_normalize_status(status),
        owner_text=(str(owner_text or "").strip() or None),
        due_date=(str(due_date or "").strip() or None),
        urgency=_normalize_urgency(urgency),
        source_kind=(str(source_kind or "").strip().lower() or "manual"),
        source_snapshot_id=(int(source_snapshot_id) if source_snapshot_id is not None else None),
        notes=(str(notes or "").strip() or None),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks_for_program(db: Session, *, program_id: int, include_done: bool = True) -> list[ExperimentTask]:
    q = db.query(ExperimentTask).filter(ExperimentTask.program_id == int(program_id))
    if not include_done:
        q = q.filter(ExperimentTask.status != "done")
        return q.order_by(*_open_sort_clause()).all()
    return q.order_by(*_sort_clause()).all()


def list_tasks_for_molecule(db: Session, *, molecule_id: int, include_done: bool = True) -> list[ExperimentTask]:
    q = db.query(ExperimentTask).filter(ExperimentTask.molecule_id == int(molecule_id))
    if not include_done:
        q = q.filter(ExperimentTask.status != "done")
        return q.order_by(*_open_sort_clause()).all()
    return q.order_by(*_sort_clause()).all()


def update_task_status(db: Session, *, task_id: int, status: str) -> ExperimentTask:
    task = db.get(ExperimentTask, int(task_id))
    if task is None:
        raise KeyError("ExperimentTask not found")
    next_status = _normalize_status(status)
    cur_status = _normalize_status(task.status)
    if cur_status == "done" and next_status != "done":
        raise ValueError("done_task_is_terminal")
    if cur_status != next_status and next_status not in ALLOWED_TRANSITIONS.get(cur_status, set()):
        raise ValueError("invalid_task_transition")
    if cur_status != next_status:
        task.status = next_status
        task.updated_at = now_utc()
        db.add(task)
        db.commit()
        db.refresh(task)
    return task


def assign_task_owner(db: Session, *, task_id: int, owner_text: str) -> ExperimentTask:
    task = db.get(ExperimentTask, int(task_id))
    if task is None:
        raise KeyError("ExperimentTask not found")
    task.owner_text = (str(owner_text or "").strip() or None)
    task.updated_at = now_utc()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def set_task_due_date(db: Session, *, task_id: int, due_date: str) -> ExperimentTask:
    task = db.get(ExperimentTask, int(task_id))
    if task is None:
        raise KeyError("ExperimentTask not found")
    task.due_date = (str(due_date or "").strip() or None)
    task.updated_at = now_utc()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def set_task_urgency(db: Session, *, task_id: int, urgency: str) -> ExperimentTask:
    task = db.get(ExperimentTask, int(task_id))
    if task is None:
        raise KeyError("ExperimentTask not found")
    task.urgency = _normalize_urgency(urgency)
    task.updated_at = now_utc()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def set_task_notes(db: Session, *, task_id: int, notes: str) -> ExperimentTask:
    task = db.get(ExperimentTask, int(task_id))
    if task is None:
        raise KeyError("ExperimentTask not found")
    task.notes = (str(notes or "").strip() or None)
    task.updated_at = now_utc()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def link_task_to_data_record(db: Session, *, task_id: int, data_record_id: int) -> ExperimentTask:
    task = db.get(ExperimentTask, int(task_id))
    if task is None:
        raise KeyError("ExperimentTask not found")
    rec = db.get(DataRecord, int(data_record_id))
    if rec is None:
        raise KeyError("DataRecord not found")
    if int(task.program_id) != int(rec.program_id):
        raise ValueError("task_record_program_mismatch")
    if task.molecule_id is not None and rec.molecule_id is not None and int(task.molecule_id) != int(rec.molecule_id):
        raise ValueError("task_record_molecule_mismatch")
    task.linked_data_record_id = int(rec.id)
    task.updated_at = now_utc()
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def top_open_task_for_molecule(db: Session, *, molecule_id: int) -> ExperimentTask | None:
    return (
        db.query(ExperimentTask)
        .filter(ExperimentTask.molecule_id == int(molecule_id))
        .filter(ExperimentTask.status != "done")
        .order_by(*_open_sort_clause())
        .first()
    )
