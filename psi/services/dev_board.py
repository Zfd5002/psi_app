from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, ExperimentTask, Molecule
from psi.core.measurement_schema import measurement_cols
from psi.services.insight_engine import build_insight_bundle, summarize_trend_signals
from psi.services.trajectory import generate_trajectory_candidates, rank_trajectory_candidates
from psi.services.trends import TREND_METRIC_KEYS

_BOARD_CACHE_BY_PROGRAM_ID: dict[int, dict[str, Any]] = {}


def invalidate_program_board_cache(*, program_id: int | None = None) -> None:
    if program_id is None:
        _BOARD_CACHE_BY_PROGRAM_ID.clear()
        return
    _BOARD_CACHE_BY_PROGRAM_ID.pop(int(program_id), None)


def _safe_json_dict(raw: str | None) -> dict[str, Any]:
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _group_key(*, has_snapshot: bool, status: str, missing_count: int) -> str:
    if not has_snapshot:
        return "not_evaluated"
    st = str(status or "").strip().lower()
    if st in {"ready", "pass", "approved"}:
        return "ready"
    if missing_count > 0:
        return "missing_data"
    if st in {"blocked", "fail", "failed", "not_ready", "hold"}:
        return "failed"
    return "not_evaluated"


def _blocking_reason(bundle: dict[str, Any]) -> str:
    sbe = [x for x in (bundle.get("strongest_blocking_evidence") or []) if isinstance(x, dict)]
    if sbe:
        top = sbe[0]
        mk = str(top.get("metric_key") or "").strip()
        req = str(top.get("required_threshold") or "").strip()
        if mk and req:
            return f"{mk}: {req}"
        if mk:
            return mk
    bis = [x for x in (bundle.get("blocking_issues") or []) if isinstance(x, dict)]
    if bis:
        top = bis[0]
        gk = str(top.get("gate_key") or "").strip()
        st = str(top.get("status") or "").strip()
        if gk and st:
            return f"{gk} ({st})"
        return gk or st
    return ""


def _trend_signals_by_molecule(db: Session, *, program_id: int) -> dict[int, str]:
    cols = measurement_cols(db)
    mk_col = str(cols["name"])
    val_col = str(cols["value_num"])
    rec_fk_col = str(cols["record_fk"])
    created_col = str(cols["created_at"] or "created_at")
    placeholders = ",".join([f":m{i}" for i in range(len(TREND_METRIC_KEYS))]) or "''"
    sql = text(
        f"""
        SELECT
          dr.molecule_id AS molecule_id,
          dm.{mk_col} AS metric_key,
          dm.{val_col} AS value_num,
          COALESCE(NULLIF(dr.run_date, ''), CAST(dm.{created_col} AS TEXT), CAST(dr.created_at AS TEXT), '') AS ts,
          dm.id AS measurement_id
        FROM data_records dr
        JOIN data_measurements dm ON dm.{rec_fk_col} = dr.id
        WHERE dr.program_id = :pid
          AND dr.molecule_id IS NOT NULL
          AND dm.{mk_col} IN ({placeholders})
          AND dm.{val_col} IS NOT NULL
        ORDER BY dr.molecule_id ASC, dm.{mk_col} ASC, ts ASC, dm.id ASC
        """
    )
    params = {"pid": int(program_id)}
    params.update({f"m{i}": str(mk) for i, mk in enumerate(TREND_METRIC_KEYS)})
    rows = db.execute(sql, params).mappings().all()

    by_molecule: dict[int, dict[str, list[dict[str, Any]]]] = {}
    for r in rows:
        mid = int(r.get("molecule_id") or 0)
        mk = str(r.get("metric_key") or "")
        if mid <= 0 or not mk:
            continue
        by_molecule.setdefault(mid, {}).setdefault(mk, []).append({"value": float(r.get("value_num"))})

    out: dict[int, str] = {}
    for mid, series in sorted(by_molecule.items(), key=lambda x: x[0]):
        rows_sig = summarize_trend_signals({"series": series})
        by_key = {str(r.get("metric_key") or ""): str(r.get("signal") or "stable") for r in rows_sig if isinstance(r, dict)}
        sig = "stable"
        for mk in TREND_METRIC_KEYS:
            cur = by_key.get(str(mk), "stable")
            if cur in {"improving", "declining"}:
                sig = cur
                break
        out[int(mid)] = sig
    return out


def _warning_flags(*, bundle: dict[str, Any], trend_signal: str) -> list[str]:
    warnings: list[str] = []
    failing = [x for x in (bundle.get("failing_evidence") or []) if isinstance(x, dict)]
    supporting = [x for x in (bundle.get("strongest_supporting_evidence") or []) if isinstance(x, dict)]
    blocking = [x for x in (bundle.get("strongest_blocking_evidence") or []) if isinstance(x, dict)]
    if failing:
        warnings.append("confirmation recommended")
    if supporting and blocking:
        warnings.append("conflicting evidence")
    if str(trend_signal) == "declining":
        warnings.append("instability risk")
    return sorted(set(warnings))


def _why_here(*, has_snapshot: bool, group_key: str, bundle: dict[str, Any], missing_metrics: list[str], blocking_reason: str) -> str:
    if not has_snapshot:
        return "Not evaluated because no DI snapshot exists."
    if group_key == "missing_data":
        mk = str(missing_metrics[0] or "").strip() if missing_metrics else ""
        if mk:
            return f"Missing data because {mk} not measured."
        return "Missing data because required metrics are not measured."
    if group_key == "failed":
        if blocking_reason:
            return f"Failed criteria because {blocking_reason}."
        failing = [x for x in (bundle.get("failing_evidence") or []) if isinstance(x, dict)]
        if failing:
            mk = str(failing[0].get("metric_key") or "").strip()
            if mk:
                return f"Failed criteria because {mk} is out of range."
        return "Failed criteria based on latest DI decision context."
    if group_key == "ready":
        return "Ready because required criteria are currently satisfied."
    return "Not currently prioritized by DI decision context."


def _task_insights_by_molecule(db: Session, *, program_id: int) -> dict[int, dict[str, Any]]:
    urgency_rank = case(
        (ExperimentTask.urgency == "critical", 0),
        (ExperimentTask.urgency == "high", 1),
        (ExperimentTask.urgency == "normal", 2),
        (ExperimentTask.urgency == "low", 3),
        else_=4,
    )
    rows = (
        db.query(ExperimentTask)
        .filter(ExperimentTask.program_id == int(program_id))
        .order_by(
            ExperimentTask.molecule_id.asc(),
            urgency_rank.asc(),
            func.coalesce(ExperimentTask.due_date, "9999-12-31").asc(),
            ExperimentTask.created_at.asc(),
            ExperimentTask.id.asc(),
        )
        .all()
    )
    by_mid: dict[int, dict[str, Any]] = {}
    for row in rows:
        mid = int(row.molecule_id)
        bucket = by_mid.setdefault(
            mid,
            {
                "open_task_count": 0,
                "in_progress_task_count": 0,
                "top_next_task_label": "",
                "top_task_status": "",
                "top_task_owner_text": "",
                "top_task_due_date": "",
                "top_task_urgency": "",
            },
        )
        st = str(row.status or "").strip().lower()
        is_open = st != "done"
        if is_open:
            bucket["open_task_count"] = int(bucket["open_task_count"]) + 1
        if st == "in_progress":
            bucket["in_progress_task_count"] = int(bucket["in_progress_task_count"]) + 1
        if is_open and not str(bucket.get("top_next_task_label") or "").strip():
            assay = str(row.suggested_assay or "").strip()
            mk = str(row.metric_key or "").strip()
            if assay and mk:
                bucket["top_next_task_label"] = f"{assay} ({mk})"
            elif assay:
                bucket["top_next_task_label"] = assay
            elif mk:
                bucket["top_next_task_label"] = mk
            else:
                bucket["top_next_task_label"] = f"Task #{int(row.id)}"
            bucket["top_task_status"] = st
            bucket["top_task_owner_text"] = str(row.owner_text or "").strip()
            bucket["top_task_due_date"] = str(row.due_date or "").strip()
            bucket["top_task_urgency"] = str(row.urgency or "").strip().lower()
    return by_mid


def _top_next_action(*, card: dict[str, Any]) -> str:
    nxt = str(card.get("top_next_task_label") or "").strip()
    if nxt:
        return f"Continue task: {nxt}"
    missing = [x for x in (card.get("missing_metrics") or []) if str(x or "").strip()]
    if missing:
        return f"Add missing measurement: {missing[0]}"
    recs = [x for x in (card.get("recommended_experiments") or []) if isinstance(x, dict)]
    if recs:
        mk = str(recs[0].get("metric_key") or "").strip()
        if mk:
            return f"Create task for suggested experiment: {mk}"
    return "Review molecule detail"


def _execution_rollup(db: Session, *, program_id: int) -> dict[str, int]:
    rows = (
        db.query(ExperimentTask)
        .filter(ExperimentTask.program_id == int(program_id))
        .order_by(ExperimentTask.id.asc())
        .all()
    )
    today = date.today()
    in_progress_this_week = 0
    overdue = 0
    blocked = 0
    unassigned = 0
    for t in rows:
        st = str(t.status or "").strip().lower()
        owner = str(t.owner_text or "").strip()
        due_raw = str(t.due_date or "").strip()
        if st == "in_progress":
            ts = t.updated_at or t.created_at
            if ts is not None and ts.date() >= (today - timedelta(days=7)):
                in_progress_this_week += 1
        if st == "blocked":
            blocked += 1
        if st != "done" and not owner:
            unassigned += 1
        if st != "done" and due_raw:
            try:
                d = date.fromisoformat(due_raw)
            except Exception:
                d = None
            if d is not None and d < today:
                overdue += 1
    return {
        "in_progress_this_week": int(in_progress_this_week),
        "overdue": int(overdue),
        "blocked": int(blocked),
        "unassigned": int(unassigned),
    }


def _trajectory_hint_by_molecule(db: Session, *, molecule_ids: list[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for mid in sorted({int(x) for x in molecule_ids if x is not None}):
        ranked = rank_trajectory_candidates(generate_trajectory_candidates(db, molecule_id=int(mid)))
        if not ranked:
            continue
        top = ranked[0]
        assay = str(top.get("suggested_assay") or "").strip()
        mk = str(top.get("metric_key") or "").strip()
        if assay and mk:
            out[int(mid)] = f"{assay} ({mk})"
        elif assay:
            out[int(mid)] = assay
        elif mk:
            out[int(mid)] = mk
    return out


def build_development_board(db: Session, *, program_id: int, use_cache: bool = True) -> dict[str, Any]:
    program_id_i = int(program_id)
    if use_cache and program_id_i in _BOARD_CACHE_BY_PROGRAM_ID:
        return _BOARD_CACHE_BY_PROGRAM_ID[program_id_i]
    molecules = (
        db.query(Molecule)
        .filter(Molecule.program_id == program_id_i)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .all()
    )
    snapshots = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.program_id == program_id_i)
        .order_by(DecisionSnapshot.molecule_id.asc(), DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )
    latest_by_molecule: dict[int, DecisionSnapshot] = {}
    for s in snapshots:
        if s.molecule_id is None:
            continue
        mid = int(s.molecule_id)
        if mid not in latest_by_molecule:
            latest_by_molecule[mid] = s

    groups: dict[str, list[dict[str, Any]]] = {
        "ready": [],
        "failed": [],
        "missing_data": [],
        "not_evaluated": [],
    }
    trend_by_molecule = _trend_signals_by_molecule(db, program_id=program_id_i)
    task_by_molecule = _task_insights_by_molecule(db, program_id=program_id_i)
    trajectory_hint_by_molecule = _trajectory_hint_by_molecule(
        db, molecule_ids=[int(m.id) for m in molecules]
    )
    for m in molecules:
        mid = int(m.id)
        snap = latest_by_molecule.get(mid)
        output = _safe_json_dict(snap.outputs_json if snap is not None else None)
        bundle = build_insight_bundle(output if output else None)
        missing = [x for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)]
        status = str(bundle.get("molecule_status") or "not_assessed")
        trend_signal = str(trend_by_molecule.get(mid) or "stable")
        missing_metrics = [str(x.get("metric_key") or "") for x in missing if str(x.get("metric_key") or "").strip()]
        blocking_reason = _blocking_reason(bundle)
        grp = _group_key(has_snapshot=(snap is not None), status=status, missing_count=len(missing_metrics))
        card = {
            "molecule_id": mid,
            "primary_id": str(m.primary_id or ""),
            "title": str(m.title or ""),
            "status": status,
            "blocking_reason": blocking_reason,
            "snapshot_id": (int(snap.id) if snap is not None else None),
            "missing_metrics": missing_metrics,
            "recommended_experiments": [x for x in (bundle.get("recommended_experiments") or []) if isinstance(x, dict)],
            "warnings": _warning_flags(bundle=bundle, trend_signal=trend_signal),
            "trend_signal": trend_signal,
            "open_task_count": int(task_by_molecule.get(mid, {}).get("open_task_count") or 0),
            "in_progress_task_count": int(task_by_molecule.get(mid, {}).get("in_progress_task_count") or 0),
            "top_next_task_label": str(task_by_molecule.get(mid, {}).get("top_next_task_label") or ""),
            "top_task_status": str(task_by_molecule.get(mid, {}).get("top_task_status") or ""),
            "top_task_owner_text": str(task_by_molecule.get(mid, {}).get("top_task_owner_text") or ""),
            "top_task_due_date": str(task_by_molecule.get(mid, {}).get("top_task_due_date") or ""),
            "top_task_urgency": str(task_by_molecule.get(mid, {}).get("top_task_urgency") or ""),
            "trajectory_next_experiment": str(trajectory_hint_by_molecule.get(mid) or ""),
            "why_here": _why_here(
                has_snapshot=(snap is not None),
                group_key=grp,
                bundle=bundle,
                missing_metrics=missing_metrics,
                blocking_reason=blocking_reason,
            ),
        }
        card["top_next_action"] = _top_next_action(card=card)
        groups[grp].append(card)

    for key in ("ready", "failed", "missing_data", "not_evaluated"):
        groups[key] = sorted(groups[key], key=lambda x: (str(x.get("primary_id") or ""), int(x.get("molecule_id") or 0)))

    out = {
        "program_id": program_id_i,
        "groups": groups,
        "execution_rollup": _execution_rollup(db, program_id=program_id_i),
    }
    if use_cache:
        _BOARD_CACHE_BY_PROGRAM_ID[program_id_i] = out
    return out
