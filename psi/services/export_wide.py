from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_registry import MeasurementDef, ordered_defs, resolve_def, conversion_to_canonical
from psi.core.export_profiles import get_profile, list_profiles
from psi.core.measurement_schema import measurement_all_cols, measurement_cols
from psi.core.models import Batch, DataRecord, Molecule


@dataclass
class ExportWideOptions:
    include_extras: bool = False
    as_of_ts: Optional[datetime.datetime] = None
    # If None, treated as "not specified" and may be filled by an export profile.
    qc_mode: Optional[str] = None  # none|model_safe|strict
    # Named export profile (optional). When set, controls column inclusion and QC defaults.
    profile: Optional[str] = None


def _iso(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, (datetime.date, datetime.datetime)):
        try:
            return x.isoformat()
        except Exception:
            return str(x)
    return str(x)


def _safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    try:
        s = str(x).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _parse_dt(x: Any) -> Optional[datetime.datetime]:
    if x is None:
        return None
    if isinstance(x, datetime.datetime):
        dt = x
    else:
        s = str(x).strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(s)
        except Exception:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def _effective_qc_mode(options: ExportWideOptions, *, profile_name: Optional[str]) -> str:
    """Resolve the QC mode to use.

    Rules:
      - If caller explicitly set qc_mode, it wins.
      - Else if a profile is selected and provides a default qc_mode, use it.
      - Else default to "none" (backward-compatible).
    """
    if options.qc_mode is not None and str(options.qc_mode).strip() != "":
        return str(options.qc_mode).strip()
    prof = get_profile(profile_name)
    if prof and prof.defaults.qc_mode:
        return prof.defaults.qc_mode
    return "none"


def _best_measurement_row(
    rows: List[Dict[str, Any]],
    *,
    is_primary_col: Optional[str],
    produced_at_col: Optional[str],
    created_at_col: Optional[str],
    id_col: Optional[str],
    ignore_col: Optional[str],
    as_of_ts: Optional[datetime.datetime],
    qc_mode: str = "none",
    qc_status_key: str = "qc_status",
    qc_policy_key: str = "qc_ignore_policy",
) -> Optional[Dict[str, Any]]:
    """Pick a deterministic 'best' measurement among candidate rows.

    Semantics:
      - If ignore_for_model is present and true -> excluded
      - If as_of_ts is provided -> only consider rows with timestamp <= as_of_ts
        (timestamp = produced_at if parseable else created_at if parseable; if neither parseable -> excluded)
      - Prefer is_primary when available, then newest timestamp, then highest id.
    """
    candidates: List[Tuple[Tuple[int, datetime.datetime, int], Dict[str, Any]]] = []

    for r in rows:
        if ignore_col:
            try:
                if int(r.get(ignore_col) or 0) == 1:
                    continue
            except Exception:
                pass

        # QC filtering (explicit; defaults are unchanged when qc_mode='none')
        if qc_mode and qc_mode != 'none':
            status = str(r.get(qc_status_key) or 'unreviewed').strip().lower()
            pol = str(r.get(qc_policy_key) or 'include').strip().lower()
            if qc_mode == 'model_safe':
                if pol in ('exclude_soft', 'exclude_hard', 'quarantine'):
                    continue
                if status == 'quarantined':
                    continue
            elif qc_mode == 'strict':
                if status != 'approved':
                    continue
                if pol != 'include':
                    continue

        dt = None
        if produced_at_col:
            dt = _parse_dt(r.get(produced_at_col))
        if dt is None and created_at_col:
            dt = _parse_dt(r.get(created_at_col))

        if as_of_ts is not None:
            if dt is None:
                continue
            if dt > as_of_ts:
                continue

        pri = 0
        if is_primary_col:
            try:
                pri = int(r.get(is_primary_col) or 0)
            except Exception:
                pri = 0

        mid = 0
        if id_col:
            try:
                mid = int(r.get(id_col) or 0)
            except Exception:
                mid = 0

        candidates.append(((pri, dt or datetime.datetime.min, mid), r))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]



def _record_effective_ts(rec: DataRecord) -> Optional[datetime.datetime]:
    """Best-effort timestamp for leakage-safe --as-of filtering.

    Priority:
      - DataRecord.run_date (ISO date/datetime string)
      - created_at
      - updated_at
    """
    dt = _parse_dt(getattr(rec, "run_date", None))
    if dt is None:
        dt = _parse_dt(getattr(rec, "created_at", None))
    if dt is None:
        dt = _parse_dt(getattr(rec, "updated_at", None))
    return dt


def _filter_records_as_of(records: List[DataRecord], as_of_ts: datetime.datetime) -> List[DataRecord]:
    """Filter DataRecord rows to those with timestamp <= as_of_ts.

    If a record has no parseable timestamp, it is excluded (safer than leaking existence).
    """
    out: List[DataRecord] = []
    for r in records:
        dt = _record_effective_ts(r)
        if dt is None:
            continue
        if dt <= as_of_ts:
            out.append(r)
    return out


def export_wide_to_csv(
    db: Session,
    *,
    out_path: str,
    options: Optional[ExportWideOptions] = None,
) -> Dict[str, Any]:
    """Export a deterministic, registry-driven wide table of data records + measurements."""

    options = options or ExportWideOptions()

    # Load records with stable ordering.
    # Deterministic: molecule_id, batch_id (NULLS LAST), run_date, record_id.
    records: List[DataRecord] = (
        db.query(DataRecord)
        .order_by(
            DataRecord.molecule_id.asc(),
            (DataRecord.batch_id.is_(None)).asc(),
            DataRecord.batch_id.asc(),
            DataRecord.run_date.asc(),
            DataRecord.id.asc(),
        )
        .all()
    )

    if options.as_of_ts is not None:
        records = _filter_records_as_of(records, options.as_of_ts)

    # Prefetch molecules/batches in-memory (avoid N+1 without over-optimizing).
    mol_by_id: Dict[int, Molecule] = {m.id: m for m in db.query(Molecule).all()}
    batch_by_id: Dict[int, Batch] = {b.id: b for b in db.query(Batch).all()}

    # Resolve profile (if any).
    profile = None
    if options.profile:
        profile = get_profile(options.profile)
        if not profile:
            raise ValueError(
                f"Unknown export profile '{options.profile}'. Available: {', '.join(list_profiles())}"
            )

    qc_mode = _effective_qc_mode(options, profile_name=profile.name if profile else None)

    # Reflect measurement table (canonicalized across PSI versions).
    mcols = measurement_cols(db)
    all_cols = measurement_all_cols(db)

    # Fetch all measurement rows for these records in one go.
    rids = [r.id for r in records]
    mrows: List[Dict[str, Any]] = []
    if rids:
        # Chunk to stay safe on SQLite parameter limits.
        CHUNK = 900
        for i in range(0, len(rids), CHUNK):
            chunk = rids[i : i + CHUNK]
            placeholders = ",".join([":r%d" % j for j in range(len(chunk))])
            params = {"r%d" % j: chunk[j] for j in range(len(chunk))}
            q = text(
                f"SELECT * FROM data_measurements WHERE {mcols['record_fk']} IN ({placeholders})"
            )
            mrows.extend(db.execute(q, params).mappings().all())

    # SQLAlchemy returns RowMapping objects from .mappings(); they are immutable.
    # Convert to plain dicts so we can safely enrich rows (qc_status, etc.).
    if mrows:
        mrows = [dict(r) for r in mrows]

    # Attach QC latest-state (optional; only when explicitly requested).
    if qc_mode != "none" and mrows:
        # Guard: tables may not exist on older DBs
        has_qc = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='measurement_qc'")).scalar()
        if has_qc:
            mids = [int(r.get(mcols.get("id") or "id")) for r in mrows if r.get(mcols.get("id") or "id") is not None]
            qc_map: Dict[int, Dict[str, Any]] = {}
            if mids:
                CHUNK2 = 900
                for j in range(0, len(mids), CHUNK2):
                    chunk = mids[j : j + CHUNK2]
                    placeholders = ",".join([":m%d" % k for k in range(len(chunk))])
                    params = {"m%d" % k: chunk[k] for k in range(len(chunk))}
                    q2 = text(f"SELECT measurement_id, status, ignore_policy FROM measurement_qc WHERE measurement_id IN ({placeholders})")
                    for r2 in db.execute(q2, params).mappings().all():
                        qc_map[int(r2["measurement_id"])] = {
                            "qc_status": (r2.get("status") or "unreviewed"),
                            "qc_ignore_policy": (r2.get("ignore_policy") or "include"),
                        }
            for r in mrows:
                try:
                    mid = int(r.get(mcols.get("id") or "id"))
                except Exception:
                    continue
                st = qc_map.get(mid)
                if st:
                    r["qc_status"] = st["qc_status"]
                    r["qc_ignore_policy"] = st["qc_ignore_policy"]
                else:
                    r["qc_status"] = "unreviewed"
                    r["qc_ignore_policy"] = "include"

    # Group measurement rows by record_id and normalized key.
    by_record: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
    name_col = mcols["name"]
    rec_col = mcols["record_fk"]
    assert name_col and rec_col

    extras_seen: set[str] = set()

    for r in mrows:
        rid = r.get(rec_col)
        try:
            rid_int = int(rid)
        except Exception:
            continue

        raw_name = str(r.get(name_col) or "").strip()
        if not raw_name:
            continue

        defn = resolve_def(raw_name)
        if defn:
            key = defn.canonical_key
        else:
            key = raw_name
            if options.include_extras:
                extras_seen.add(key)
            else:
                continue

        by_record.setdefault(rid_int, {}).setdefault(key, []).append(dict(r))

    # Build header (deterministic)
    default_core_cols = [
        "molecule_id",
        "molecule_primary_id",
        "molecule_title",
        "batch_id",
        "batch_label",
        "record_id",
        "run_date",
        "domain",
        "data_type",
        "method",
        "title",
        "primary_result_text",
    ]

    core_cols = list(profile.core_columns) if (profile and profile.core_columns) else list(default_core_cols)

    if profile:
        defs: List[MeasurementDef] = []
        for k in profile.measurement_keys:
            d = resolve_def(k)
            if not d:
                raise RuntimeError(f"Profile '{profile.name}' references unknown measurement key '{k}'")
            defs.append(d)
    else:
        defs = list(ordered_defs())

    meas_cols: List[str] = []
    for d in defs:
        meas_cols.append(d.export_name)
        # Always include unit when canonical_unit defined (small, helpful)
        if d.canonical_unit:
            meas_cols.append(f"{d.export_name}__unit")
        # Raw transparency
        meas_cols.append(f"{d.export_name}__raw_value")
        meas_cols.append(f"{d.export_name}__raw_unit")
        # Provenance (per-measurement)
        meas_cols.extend(
            [
                f"{d.export_name}__producer",
                f"{d.export_name}__producer_version",
                f"{d.export_name}__source_path",
                f"{d.export_name}__run_id",
                f"{d.export_name}__produced_at",
            ]
        )

    extra_cols: List[str] = []
    if options.include_extras and extras_seen:
        for k in sorted(extras_seen, key=lambda x: str(x)):
            # keep normalization light; exporter users can post-process
            safe = str(k).strip().replace(" ", "_")
            extra_cols.append(f"extras__{safe}")

    header = core_cols + meas_cols + extra_cols

    # Write CSV
    rows_written = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()

        for rec in records:
            mol = mol_by_id.get(rec.molecule_id) if rec.molecule_id else None
            bat = batch_by_id.get(rec.batch_id) if rec.batch_id else None

            out: Dict[str, Any] = {
                "molecule_id": rec.molecule_id or "",
                "molecule_primary_id": getattr(mol, "primary_id", "") if mol else "",
                "molecule_title": getattr(mol, "title", "") if mol else "",
                "batch_id": rec.batch_id or "",
                "batch_label": getattr(bat, "batch_id", "") if bat else "",
                "record_id": rec.id,
                "run_date": _iso(rec.run_date),
                "domain": rec.domain,
                "data_type": rec.data_type,
                "method": rec.method,
                "title": rec.title,
                "primary_result_text": rec.primary_result_text or "",
            }

            # Fill registry measurements
            rec_meas = by_record.get(rec.id, {})
            for d in defs:
                candidates = rec_meas.get(d.canonical_key)
                if not candidates:
                    continue

                best = _best_measurement_row(
                    candidates,
                    is_primary_col=mcols.get("is_primary"),
                    produced_at_col=mcols.get("produced_at"),
                    created_at_col=mcols.get("created_at") or mcols.get("updated_at"),
                    id_col=mcols.get("id"),
                    ignore_col=mcols.get("ignore_for_model"),
                    as_of_ts=options.as_of_ts,
                    qc_mode=qc_mode,
                )
                if not best:
                    continue

                raw_num = _safe_float(best.get(mcols.get("value_num") or ""))
                raw_text = best.get(mcols.get("value_text") or "")
                raw_unit = best.get(mcols.get("unit") or "")
                raw_unit_s = str(raw_unit) if raw_unit is not None else ""

                # Raw output fields
                if raw_num is not None:
                    out[f"{d.export_name}__raw_value"] = raw_num
                elif raw_text is not None and str(raw_text).strip():
                    out[f"{d.export_name}__raw_value"] = str(raw_text).strip()
                else:
                    out[f"{d.export_name}__raw_value"] = ""

                out[f"{d.export_name}__raw_unit"] = raw_unit_s

                # Canonical unit
                if d.canonical_unit:
                    out[f"{d.export_name}__unit"] = d.canonical_unit

                # Canonical converted value (only explicit, no guessing)
                if d.dtype == "numeric" and raw_num is not None:
                    fn = conversion_to_canonical(d, raw_unit_s) if raw_unit_s else None
                    if fn:
                        try:
                            out[d.export_name] = fn(raw_num)
                        except Exception:
                            out[d.export_name] = ""
                    elif d.canonical_unit and raw_unit_s == d.canonical_unit:
                        out[d.export_name] = raw_num
                    else:
                        # Unknown/missing unit or no conversion rule
                        out[d.export_name] = ""
                else:
                    # text measurement
                    if raw_text is not None and str(raw_text).strip():
                        out[d.export_name] = str(raw_text).strip()

                # Provenance if present
                out[f"{d.export_name}__producer"] = str(best.get(mcols.get("producer") or "") or "")
                out[f"{d.export_name}__producer_version"] = str(best.get(mcols.get("producer_version") or "") or "")
                out[f"{d.export_name}__source_path"] = str(best.get(mcols.get("source_path") or "") or "")
                out[f"{d.export_name}__run_id"] = str(best.get(mcols.get("run_id") or "") or "")
                out[f"{d.export_name}__produced_at"] = str(best.get(mcols.get("produced_at") or "") or "")

            # Extras
            if options.include_extras and extra_cols:
                for k in sorted(extras_seen, key=lambda x: str(x)):
                    safe = str(k).strip().replace(" ", "_")
                    col = f"extras__{safe}"
                    candidates = rec_meas.get(k)
                    if not candidates:
                        out[col] = ""
                        continue
                    best = _best_measurement_row(
                        candidates,
                        is_primary_col=mcols.get("is_primary"),
                        produced_at_col=mcols.get("produced_at"),
                        created_at_col=mcols.get("created_at") or mcols.get("updated_at"),
                        id_col=mcols.get("id"),
                        ignore_col=mcols.get("ignore_for_model"),
                        as_of_ts=options.as_of_ts,
                        qc_mode=qc_mode,
                    )
                    if not best:
                        out[col] = ""
                        continue
                    raw_num = _safe_float(best.get(mcols.get("value_num") or ""))
                    raw_text = best.get(mcols.get("value_text") or "")
                    if raw_num is not None:
                        out[col] = raw_num
                    else:
                        out[col] = str(raw_text).strip() if raw_text is not None else ""

            w.writerow({k: out.get(k, "") for k in header})
            rows_written += 1

    return {
        "rows": rows_written,
        "columns": len(header),
        "include_extras": options.include_extras,
    }
    
# Backwards/CLI compatibility: older scripts may import export_wide_csv
def export_wide_csv(db: Session, out_path: str, include_extras: bool = False) -> str:
    """
    CLI compatibility wrapper.

    The service API uses ExportWideOptions; the CLI historically passed include_extras directly.
    """
    opts = ExportWideOptions(include_extras=bool(include_extras))
    return export_wide_to_csv(db=db, out_path=out_path, options=opts)
