from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from psi.core.db import SessionLocal, ensure_schema


def _looks_percent(name: str, unit: Optional[str]) -> bool:
    n = (name or "").lower()
    if unit == "%":
        return True
    return n.endswith("percent") or n.endswith("_percent") or "%" in n


def run(
    *,
    only_types: Optional[List[str]] = None,
    program_id: Optional[int] = None,
    dry_run: bool = True,
    limit: int = 0,
) -> int:
    ensure_schema()
    db = SessionLocal()

    # Detect columns conservatively
    cols = {r["name"] for r in db.execute(text("PRAGMA table_info(data_measurements)")).mappings().all()}
    if "data_record_id" not in cols and "record_id" not in cols:
        raise RuntimeError("data_measurements missing record FK column")

    record_fk = "data_record_id" if "data_record_id" in cols else "record_id"
    qc_flag = "qc_flag" if "qc_flag" in cols else ("qc_status" if "qc_status" in cols else None)
    qc_note = "qc_note" if "qc_note" in cols else ("qc_reason" if "qc_reason" in cols else None)
    if not qc_flag:
        # Tool can still report issues, but cannot persist flags.
        qc_flag = None

    where = ["1=1"]
    params: Dict[str, Any] = {}
    if only_types and "data_type" in cols:
        where.append("data_type IN :types")
        params["types"] = tuple(sorted({t.strip() for t in only_types if t.strip()}))
    if program_id is not None:
        # Join to data_records for program filter
        where.append("dr.program_id = :pid")
        params["pid"] = int(program_id)

    lim_sql = f"LIMIT {int(limit)}" if limit and limit > 0 else ""

    q = text(
        f"""
        SELECT dm.*
        FROM data_measurements dm
        JOIN data_records dr ON dr.id = dm.{record_fk}
        WHERE {' AND '.join(where)}
        ORDER BY dm.id ASC
        {lim_sql}
        """
    )
    rows = db.execute(q, params).mappings().all()

    flagged = 0
    issues: List[Dict[str, Any]] = []

    for r in rows:
        name = str(r.get("name") or r.get("key") or "").strip()
        unit = r.get("unit")
        val_num = r.get("value_num")
        if name and _looks_percent(name, unit):
            if val_num is None:
                continue
            try:
                x = float(val_num)
            except Exception:
                continue
            if x < 0 or x > 100:
                issues.append(
                    {
                        "id": r.get("id"),
                        "record_id": r.get(record_fk),
                        "name": name,
                        "value_num": x,
                        "reason": "percent_out_of_bounds",
                    }
                )

    if dry_run or not qc_flag:
        print(f"DRY-RUN: {len(issues)} issue(s) detected. Persist={bool(qc_flag and not dry_run)}")
        for row in issues[:10]:
            print(" ", row)
        return 0 if not issues else 2

    # Persist flags idempotently (set only when empty)
    for it in issues:
        mid = it["id"]
        if mid is None:
            continue
        # Only flag if currently unflagged
        cur = db.execute(text("SELECT " + qc_flag + " FROM data_measurements WHERE id=:id"), {"id": mid}).scalar()
        if cur not in (None, 0, "0", ""):
            continue
        upd_cols = [f"{qc_flag}=1"]
        upd_params = {"id": mid}
        if qc_note:
            upd_cols.append(f"{qc_note}=:note")
            upd_params["note"] = it["reason"]
        db.execute(text("UPDATE data_measurements SET " + ", ".join(upd_cols) + " WHERE id=:id"), upd_params)
        flagged += 1
    db.commit()

    print(f"OK: flagged {flagged} measurement(s) out of {len(issues)} issue(s)")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.qc_measurements",
        description="Conservative QC checks for data_measurements (CLI-only).",
    )
    ap.add_argument("--only-types", default="", help="Comma-separated data_type values")
    ap.add_argument("--program-id", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    only_types = [t.strip() for t in args.only_types.split(",") if t.strip()] or None
    program_id = int(args.program_id) if int(args.program_id or 0) > 0 else None
    dry_run = True if args.dry_run else False

    raise SystemExit(
        run(only_types=only_types, program_id=program_id, dry_run=dry_run, limit=int(args.limit))
    )


if __name__ == "__main__":
    main()
