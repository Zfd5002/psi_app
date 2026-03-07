from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.models import DecisionSnapshot, Molecule
from psi.core.measurement_schema import measurement_cols
from psi.services.insight_engine import build_insight_bundle, summarize_trend_signals
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
    for m in molecules:
        mid = int(m.id)
        snap = latest_by_molecule.get(mid)
        output = _safe_json_dict(snap.outputs_json if snap is not None else None)
        bundle = build_insight_bundle(output if output else None)
        missing = [x for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)]
        status = str(bundle.get("molecule_status") or "not_assessed")
        trend_signal = str(trend_by_molecule.get(mid) or "stable")
        card = {
            "molecule_id": mid,
            "primary_id": str(m.primary_id or ""),
            "title": str(m.title or ""),
            "status": status,
            "blocking_reason": _blocking_reason(bundle),
            "snapshot_id": (int(snap.id) if snap is not None else None),
            "missing_metrics": [str(x.get("metric_key") or "") for x in missing if str(x.get("metric_key") or "").strip()],
            "recommended_experiments": [x for x in (bundle.get("recommended_experiments") or []) if isinstance(x, dict)],
            "warnings": _warning_flags(bundle=bundle, trend_signal=trend_signal),
            "trend_signal": trend_signal,
        }
        grp = _group_key(has_snapshot=(snap is not None), status=status, missing_count=len(card["missing_metrics"]))
        groups[grp].append(card)

    for key in ("ready", "failed", "missing_data", "not_evaluated"):
        groups[key] = sorted(groups[key], key=lambda x: (str(x.get("primary_id") or ""), int(x.get("molecule_id") or 0)))

    out = {"program_id": program_id_i, "groups": groups}
    if use_cache:
        _BOARD_CACHE_BY_PROGRAM_ID[program_id_i] = out
    return out
