from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.core.measurement_registry import MeasurementDef, ordered_defs, resolve_def, conversion_to_canonical
from psi.core.models import Batch, DataRecord, Molecule


@dataclass
class ExportWideOptions:
    include_extras: bool = False


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


def _measurement_cols(db: Session) -> Tuple[Dict[str, Optional[str]], set[str]]:
    """Local reflection helper (mirrors psi.services.measurements but scoped to exporter)."""
    rows = db.execute(text("PRAGMA table_info(data_measurements)")).mappings().all()
    cols = {str(r["name"]) for r in rows}

    def pick(*names: str) -> Optional[str]:
        for n in names:
            if n in cols:
                return n
        return None

    mapping = {
        "id": pick("id"),
        "record_fk": pick("data_record_id", "record_id"),
        "name": pick("metric_key", "name", "key"),
        "value_num": pick("value_num", "numeric_value", "value"),
        "value_text": pick("value_text", "text_value", "raw_value"),
        "unit": pick("unit"),
        "comparator": pick("comparator", "op"),
        "is_primary": pick("is_primary", "primary", "is_headline"),
        "created_at": pick("created_at"),
        "updated_at": pick("updated_at"),
        "producer": pick("producer", "tool_name", "producer_name"),
        "producer_version": pick("producer_version", "tool_version"),
        "source_path": pick("source_path", "source_id", "extraction_path"),
        "run_id": pick("run_id"),
        "produced_at": pick("produced_at"),
        "notes": pick("notes"),
    }

    if not mapping["record_fk"] or not mapping["name"]:
        raise RuntimeError(f"data_measurements schema missing expected columns. Found: {sorted(cols)}")

    return mapping, cols


def _best_measurement_row(
    rows: List[Dict[str, Any]],
    *,
    is_primary_col: Optional[str],
    produced_at_col: Optional[str],
    created_at_col: Optional[str],
    id_col: Optional[str],
) -> Dict[str, Any]:
    """Pick a deterministic 'best' measurement among candidate rows.

    Semantics: prefer is_primary when available, then newest produced_at/created_at, then highest id.
    """

    def score(r: Dict[str, Any]) -> Tuple[int, str, int]:
        pri = 0
        if is_primary_col:
            try:
                pri = int(r.get(is_primary_col) or 0)
            except Exception:
                pri = 0
        ts = ""
        if produced_at_col:
            ts = str(r.get(produced_at_col) or "")
        if not ts and created_at_col:
            ts = str(r.get(created_at_col) or "")
        mid = 0
        if id_col:
            try:
                mid = int(r.get(id_col) or 0)
            except Exception:
                mid = 0
        return (pri, ts, mid)

    # max score wins
    return sorted(rows, key=score, reverse=True)[0]


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

    # Prefetch molecules/batches in-memory (avoid N+1 without over-optimizing).
    mol_by_id: Dict[int, Molecule] = {m.id: m for m in db.query(Molecule).all()}
    batch_by_id: Dict[int, Batch] = {b.id: b for b in db.query(Batch).all()}

    # Reflect measurement table.
    mcols, all_cols = _measurement_cols(db)

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
    core_cols = [
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
                )

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
                    )
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
