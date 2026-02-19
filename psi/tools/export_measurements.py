from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from psi.services.measurements import get_primary_measurement_for_record


def _require_export_enabled() -> None:
    if os.environ.get("PSI_ENABLE_EXPORT") != "1":
        raise RuntimeError(
            "Export is disabled. Set PSI_ENABLE_EXPORT=1 to enable explicit exports."
        )


def _parse_dt(s: Optional[str]) -> Optional[str]:
    """Return ISO string for safe SQL comparison, or None."""
    if not s:
        return None
    s = str(s).strip()
    if not s:
        return None
    # Accept YYYY-MM-DD or ISO datetime.
    try:
        if len(s) == 10:
            return datetime.fromisoformat(s + "T00:00:00").isoformat()
        return datetime.fromisoformat(s.replace("Z", "")).isoformat()
    except Exception:
        # If user passes something odd, fail loudly (export is explicit).
        raise ValueError(f"Invalid datetime filter: {s!r}")


def export_csv(
    db: Session,
    out_path: Path,
    *,
    program_id: Optional[int] = None,
    molecule_id: Optional[int] = None,
    data_type: Optional[str] = None,
    method: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    include_qc: bool = False,
    wide: bool = False,
) -> Path:
    """Export DataRecords and (optionally) their primary measurement in a stable format.

    Export is explicitly gated by PSI_ENABLE_EXPORT=1.
    """

    _require_export_enabled()

    after_iso = _parse_dt(after)
    before_iso = _parse_dt(before)

    where = ["1=1"]
    params: Dict[str, Any] = {}
    if program_id is not None:
        where.append("program_id=:program_id")
        params["program_id"] = int(program_id)
    if molecule_id is not None:
        where.append("molecule_id=:molecule_id")
        params["molecule_id"] = int(molecule_id)
    if data_type:
        where.append("data_type=:data_type")
        params["data_type"] = str(data_type)
    if method:
        where.append("method=:method")
        params["method"] = str(method)
    if after_iso:
        where.append("created_at >= :after")
        params["after"] = after_iso
    if before_iso:
        where.append("created_at <= :before")
        params["before"] = before_iso

    # Stable ordering: newest first, deterministic ties.
    q = text(
        f"""
        SELECT id, program_id, molecule_id, batch_id, domain, data_type, method, title, run_date, run_at, created_at
        FROM data_records
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC, id DESC
        """
    )
    rows = db.execute(q, params).mappings().all()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if wide:
        header = [
            "record_id",
            "program_id",
            "molecule_id",
            "batch_id",
            "domain",
            "data_type",
            "method",
            "title",
            "run_date",
            "run_at",
            "created_at",
            "primary_name",
            "primary_value_num",
            "primary_value_text",
            "primary_unit",
            "primary_comparator",
        ]
        # qc flag is optional; we include column but may be blank
        header.append("primary_qc_flag")

        with out_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            for r in rows:
                meas = get_primary_measurement_for_record(
                    db, int(r["id"]), include_qc=bool(include_qc)
                )
                w.writerow(
                    [
                        r["id"],
                        r["program_id"],
                        r.get("molecule_id"),
                        r.get("batch_id"),
                        r.get("domain"),
                        r.get("data_type"),
                        r.get("method"),
                        r.get("title"),
                        r.get("run_date"),
                        r.get("run_at"),
                        r.get("created_at"),
                        (meas or {}).get("name"),
                        (meas or {}).get("value_num"),
                        (meas or {}).get("value_text"),
                        (meas or {}).get("unit"),
                        (meas or {}).get("comparator"),
                        (meas or {}).get("qc_flag"),
                    ]
                )
        return out_path

    # Non-wide export: record-only.
    header = [
        "record_id",
        "program_id",
        "molecule_id",
        "batch_id",
        "domain",
        "data_type",
        "method",
        "title",
        "run_date",
        "run_at",
        "created_at",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(
                [
                    r["id"],
                    r["program_id"],
                    r.get("molecule_id"),
                    r.get("batch_id"),
                    r.get("domain"),
                    r.get("data_type"),
                    r.get("method"),
                    r.get("title"),
                    r.get("run_date"),
                    r.get("run_at"),
                    r.get("created_at"),
                ]
            )

    return out_path
