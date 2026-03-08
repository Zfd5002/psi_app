from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from psi.core.models import DataRecord, DecisionSnapshot, ExperimentTask, Molecule, Program
from psi.services.dev_board import build_development_board
from psi.services.insight_engine import build_insight_bundle
import json


def _molecule_group_totals(db: Session) -> tuple[int, int]:
    ready = 0
    missing = 0
    programs = db.query(Program).order_by(Program.id.asc()).all()
    for p in programs:
        board = build_development_board(db, program_id=int(p.id), use_cache=False)
        groups = board.get("groups") if isinstance(board, dict) else {}
        if not isinstance(groups, dict):
            continue
        ready += len(groups.get("ready") or [])
        missing += len(groups.get("missing_data") or [])
    return int(ready), int(missing)


def build_portfolio_summary(db: Session) -> dict[str, int]:
    today = date.today()
    programs = int(db.query(Program).count())
    molecules = int(db.query(Molecule).count())
    tasks = db.query(ExperimentTask).order_by(ExperimentTask.id.asc()).all()
    overdue = 0
    blocked = 0
    in_progress = 0
    unassigned = 0
    for t in tasks:
        st = str(t.status or "").strip().lower()
        due = str(t.due_date or "").strip()
        owner = str(t.owner_text or "").strip()
        if st == "blocked":
            blocked += 1
        if st == "in_progress":
            in_progress += 1
        if st != "done" and not owner:
            unassigned += 1
        if st != "done" and due:
            try:
                d = date.fromisoformat(due)
            except Exception:
                d = None
            if d is not None and d < today:
                overdue += 1
    ready, missing = _molecule_group_totals(db)
    return {
        "program_count": int(programs),
        "molecule_count": int(molecules),
        "task_count": int(len(tasks)),
        "overdue_tasks": int(overdue),
        "blocked_tasks": int(blocked),
        "tasks_in_progress": int(in_progress),
        "tasks_overdue": int(overdue),
        "tasks_blocked": int(blocked),
        "tasks_unassigned": int(unassigned),
        "ready_molecules": int(ready),
        "missing_data_molecules": int(missing),
    }


def build_program_portfolio_summary(db: Session, *, program_id: int) -> dict[str, int]:
    pid = int(program_id)
    board = build_development_board(db, program_id=pid, use_cache=False)
    groups = board.get("groups") if isinstance(board, dict) else {}
    if not isinstance(groups, dict):
        groups = {}
    molecules_ready = int(len(groups.get("ready") or []))
    molecules_failed = int(len(groups.get("failed") or []))
    molecules_missing = int(len(groups.get("missing_data") or []))

    today = date.today()
    rows = (
        db.query(ExperimentTask)
        .filter(ExperimentTask.program_id == pid)
        .order_by(ExperimentTask.id.asc())
        .all()
    )
    open_tasks = 0
    overdue_tasks = 0
    blocked_tasks = 0
    for t in rows:
        st = str(t.status or "").strip().lower()
        due = str(t.due_date or "").strip()
        if st != "done":
            open_tasks += 1
        if st == "blocked":
            blocked_tasks += 1
        if st != "done" and due:
            try:
                d = date.fromisoformat(due)
            except Exception:
                d = None
            if d is not None and d < today:
                overdue_tasks += 1
    return {
        "program_id": pid,
        "molecules_ready": molecules_ready,
        "molecules_failed": molecules_failed,
        "molecules_missing_data": molecules_missing,
        "open_tasks": int(open_tasks),
        "overdue_tasks": int(overdue_tasks),
        "blocked_tasks": int(blocked_tasks),
    }


def _readiness_score(row: dict[str, int]) -> float:
    ready = float(row.get("molecules_ready") or 0)
    failed = float(row.get("molecules_failed") or 0)
    missing = float(row.get("molecules_missing_data") or 0)
    open_tasks = float(row.get("open_tasks") or 0)
    blocked = float(row.get("blocked_tasks") or 0)
    overdue = float(row.get("overdue_tasks") or 0)
    # Portfolio heuristic only (read-model): rewards readiness, penalizes evidence gaps and execution burden.
    return (2.0 * ready) - (1.5 * failed) - (1.0 * missing) - (0.25 * open_tasks) - (0.5 * blocked) - (0.5 * overdue)


def _program_heat(row: dict[str, int | float]) -> tuple[str, str]:
    blocked = int(row.get("blocked_tasks") or 0)
    missing = int(row.get("molecules_missing_data") or 0)
    ready = int(row.get("molecules_ready") or 0)
    if blocked > 0:
        return ("blocked", "🔴")
    if missing > 0 and ready <= 0:
        return ("evidence_gaps", "🟡")
    return ("progressing", "🟢")


def _program_bottleneck_badges(db: Session, *, program_id: int, overdue_threshold: int = 3) -> list[str]:
    pid = int(program_id)
    board = build_development_board(db, program_id=pid, use_cache=False)
    groups = board.get("groups") if isinstance(board, dict) else {}
    rows = []
    if isinstance(groups, dict):
        for k in ("ready", "failed", "missing_data", "not_evaluated"):
            rows.extend([r for r in (groups.get(k) or []) if isinstance(r, dict)])
    molecule_count = max(1, len(rows))
    by_metric: dict[str, int] = {}
    for r in rows:
        for mk in (r.get("missing_metrics") or []):
            key = str(mk or "").strip()
            if not key:
                continue
            by_metric[key] = int(by_metric.get(key, 0)) + 1
    badges: list[str] = []
    if by_metric:
        top_metric, top_n = sorted(by_metric.items(), key=lambda x: (-x[1], x[0]))[0]
        if float(top_n) / float(molecule_count) > 0.5:
            badges.append(f"missing_metric_concentration:{top_metric}")
    overdue = (
        db.query(ExperimentTask)
        .filter(ExperimentTask.program_id == pid)
        .filter(ExperimentTask.status != "done")
        .filter(ExperimentTask.due_date.is_not(None))
        .all()
    )
    today = date.today()
    overdue_n = 0
    for t in overdue:
        raw = str(t.due_date or "").strip()
        if not raw:
            continue
        try:
            d = date.fromisoformat(raw)
        except Exception:
            continue
        if d < today:
            overdue_n += 1
    if overdue_n > int(overdue_threshold):
        badges.append("overdue_task_burden")
    return badges


def build_portfolio_program_summaries(db: Session) -> list[dict[str, int | float]]:
    programs = db.query(Program).order_by(Program.id.asc()).all()
    out: list[dict[str, int | float]] = []
    for p in programs:
        row = build_program_portfolio_summary(db, program_id=int(p.id))
        molecule_count = (
            db.query(Molecule)
            .filter(Molecule.program_id == int(p.id))
            .count()
        )
        row2: dict[str, int | float] = {
            **row,
            "program_name": str(p.name or ""),
            "molecule_count": int(molecule_count),
            "readiness_score": float(_readiness_score(row)),
        }
        heat_label, heat_emoji = _program_heat(row2)
        row2["heat_label"] = heat_label
        row2["heat_emoji"] = heat_emoji
        row2["bottleneck_badges"] = _program_bottleneck_badges(db, program_id=int(p.id))
        out.append(row2)
    out.sort(
        key=lambda r: (
            -float(r.get("readiness_score") or 0.0),
            int(r.get("open_tasks") or 0),
            int(r.get("molecule_count") or 0),
            int(r.get("program_id") or 0),
        )
    )
    return out


def _safe_json(raw: str | None) -> dict:
    try:
        obj = json.loads(raw or "{}")
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def build_molecule_leaderboard(db: Session, *, limit: int = 25) -> list[dict[str, int | float | str]]:
    molecules = db.query(Molecule).order_by(Molecule.id.asc()).all()
    # latest snapshot per molecule
    snaps = (
        db.query(DecisionSnapshot)
        .order_by(DecisionSnapshot.molecule_id.asc(), DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    latest_by_mid: dict[int, DecisionSnapshot] = {}
    for s in snaps:
        if s.molecule_id is None:
            continue
        mid = int(s.molecule_id)
        if mid not in latest_by_mid:
            latest_by_mid[mid] = s
    evidence_counts: dict[int, int] = {}
    for row in db.query(DataRecord.molecule_id).filter(DataRecord.molecule_id.is_not(None)).all():
        mid = int(row[0])
        evidence_counts[mid] = int(evidence_counts.get(mid, 0)) + 1

    out: list[dict[str, int | float | str]] = []
    for m in molecules:
        mid = int(m.id)
        snap = latest_by_mid.get(mid)
        bundle = build_insight_bundle(_safe_json(snap.outputs_json) if snap is not None else None)
        status = str(bundle.get("molecule_status") or "not_assessed")
        missing_n = int(len(bundle.get("missing_evidence") or []))
        evidence_n = int(evidence_counts.get(mid, 0))
        ready_bonus = 3.0 if status == "ready" else 0.0
        failed_penalty = 1.5 if status in {"blocked", "not_ready"} else 0.0
        score = ready_bonus + (0.2 * evidence_n) - (1.0 * missing_n) - failed_penalty
        out.append(
            {
                "molecule_id": mid,
                "primary_id": str(m.primary_id or ""),
                "program_id": int(m.program_id),
                "status": status,
                "completed_evidence_count": evidence_n,
                "missing_metrics_count": missing_n,
                "leaderboard_score": float(score),
            }
        )
    out.sort(
        key=lambda r: (
            -float(r.get("leaderboard_score") or 0.0),
            int(r.get("missing_metrics_count") or 0),
            -int(r.get("completed_evidence_count") or 0),
            int(r.get("molecule_id") or 0),
        )
    )
    return out[: max(1, int(limit))]


def build_evidence_gap_report(db: Session, *, limit: int = 20) -> list[dict[str, int | str]]:
    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id.is_not(None))
        .order_by(DecisionSnapshot.molecule_id.asc(), DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    latest_by_mid: dict[int, DecisionSnapshot] = {}
    for s in snaps:
        mid = int(s.molecule_id)
        if mid not in latest_by_mid:
            latest_by_mid[mid] = s
    counts: dict[str, int] = {}
    for s in latest_by_mid.values():
        bundle = build_insight_bundle(_safe_json(s.outputs_json))
        missing = [x for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)]
        for row in missing:
            mk = str(row.get("metric_key") or "").strip()
            if not mk:
                continue
            counts[mk] = int(counts.get(mk, 0)) + 1
    rows = [{"metric_key": k, "missing_molecule_count": int(v)} for k, v in counts.items()]
    rows.sort(key=lambda r: (-int(r["missing_molecule_count"]), str(r["metric_key"])))
    return rows[: max(1, int(limit))]


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _week_start(value: datetime) -> date:
    d = value.date()
    return d - timedelta(days=int(d.weekday()))


def build_portfolio_timeline(db: Session, *, weeks: int = 8) -> list[dict[str, int | str]]:
    span = max(1, int(weeks))
    today = date.today()
    current_week = today - timedelta(days=int(today.weekday()))
    starts = [current_week - timedelta(days=7 * i) for i in range(span - 1, -1, -1)]
    rows: dict[date, dict[str, int | str]] = {
        s: {
            "week_start": s.isoformat(),
            "tasks_completed": 0,
            "tasks_created": 0,
            "evidence_created": 0,
        }
        for s in starts
    }

    for t in db.query(ExperimentTask).order_by(ExperimentTask.id.asc()).all():
        created = _coerce_datetime(t.created_at)
        if created is not None:
            ws = _week_start(created)
            row = rows.get(ws)
            if row is not None:
                row["tasks_created"] = int(row["tasks_created"]) + 1
        if str(t.status or "").strip().lower() == "done":
            done_at = _coerce_datetime(t.updated_at) or created
            if done_at is not None:
                ws = _week_start(done_at)
                row = rows.get(ws)
                if row is not None:
                    row["tasks_completed"] = int(row["tasks_completed"]) + 1

    for r in db.query(DataRecord).order_by(DataRecord.id.asc()).all():
        created = _coerce_datetime(r.created_at)
        if created is None:
            continue
        ws = _week_start(created)
        row = rows.get(ws)
        if row is not None:
            row["evidence_created"] = int(row["evidence_created"]) + 1

    return [rows[s] for s in starts]


def build_portfolio_export_rows(db: Session) -> list[dict[str, int | float | str]]:
    rows = build_portfolio_program_summaries(db)
    out: list[dict[str, int | float | str]] = []
    for r in rows:
        out.append(
            {
                "program_id": int(r.get("program_id") or 0),
                "program_name": str(r.get("program_name") or ""),
                "program_status": str(r.get("heat_label") or "unknown"),
                "readiness_score": float(r.get("readiness_score") or 0.0),
                "molecule_count": int(r.get("molecule_count") or 0),
                "molecules_ready": int(r.get("molecules_ready") or 0),
                "molecules_failed": int(r.get("molecules_failed") or 0),
                "molecules_missing_data": int(r.get("molecules_missing_data") or 0),
                "open_tasks": int(r.get("open_tasks") or 0),
                "overdue_tasks": int(r.get("overdue_tasks") or 0),
                "blocked_tasks": int(r.get("blocked_tasks") or 0),
            }
        )
    return out
