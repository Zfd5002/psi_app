from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from psi.core.db import SessionLocal, ensure_schema
from psi.services.measurements import extract_measurements, upsert_measurements, upsert_measurements_force


def _iter_record_rows(
    db,
    *,
    only_types: Optional[set[str]] = None,
) -> Iterable[Dict[str, Any]]:
    where = ["is_included=1"]
    params: Dict[str, Any] = {}
    if only_types:
        where.append("data_type IN :types")
        params["types"] = tuple(sorted(only_types))

    q = text(
        f"""
        SELECT id, data_type, method, results_json, params_json
        FROM data_records
        WHERE {' AND '.join(where)}
        ORDER BY id ASC
        """
    )
    return db.execute(q, params).mappings().all()


def _has_primary(db, record_id: int) -> bool:
    # Avoid importing internal helpers; keep this tool resilient.
    try:
        row = db.execute(
            text(
                "SELECT 1 FROM data_measurements WHERE data_record_id=:rid AND is_primary=1 LIMIT 1"
            ),
            {"rid": record_id},
        ).first()
        return row is not None
    except Exception:
        # Schema variants: if column doesn't exist, treat as missing.
        return False


def run(
    *,
    only_types: Optional[List[str]] = None,
    only_missing_primary: bool = False,
    max_failures: int = 50,
    write_failures: Optional[Path] = None,
    force_overwrite: bool = False,
    dry_run: bool = False,
) -> int:
    ensure_schema()
    db = SessionLocal()

    failures: List[Dict[str, Any]] = []
    wrote_total = 0

    only_types_set = set([t.strip() for t in (only_types or []) if t.strip()]) or None

    rows = _iter_record_rows(db, only_types=only_types_set)
    for r in rows:
        rid = int(r["id"])
        if only_missing_primary and _has_primary(db, rid):
            continue

        try:
            meas = extract_measurements(
                data_type=r.get("data_type"),
                method=r.get("method"),
                results_json=r.get("results_json"),
                params_json=r.get("params_json"),
            )
            if not meas:
                continue

            if dry_run:
                # count what *would* be inserted/updated
                wrote_total += 1
                continue

            if force_overwrite:
                wrote_total += upsert_measurements_force(
                    db, record_id=rid, measurements=meas
                )
            else:
                wrote_total += upsert_measurements(db, record_id=rid, measurements=meas)

            db.commit()
        except Exception as e:
            failures.append({"record_id": rid, "error": repr(e)})
            if len(failures) >= max_failures:
                break

    if write_failures:
        write_failures = Path(write_failures)
        write_failures.parent.mkdir(parents=True, exist_ok=True)
        with write_failures.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["record_id", "error"])
            w.writeheader()
            for row in failures:
                w.writerow(row)

    if dry_run:
        print(f"DRY-RUN: would touch ~{wrote_total} record(s); failures={len(failures)}")
    else:
        print(f"OK: wrote {wrote_total} measurement row(s); failures={len(failures)}")

    if failures:
        print("First few failures:")
        for row in failures[:5]:
            print(" ", row)

    return 0 if not failures else 2


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m psi.tools.backfill_measurements",
        description="Backfill data_measurements from existing data_records (SAFE by default).",
    )
    ap.add_argument("--only-types", default="", help="Comma-separated data_type values")
    ap.add_argument(
        "--only-missing-primary",
        action="store_true",
        help="Only process records lacking a primary measurement (best-effort).",
    )
    ap.add_argument("--max-failures", type=int, default=50)
    ap.add_argument("--write-failures", default="", help="Path to CSV of failures")
    ap.add_argument("--force-overwrite", action="store_true", help="Overwrite existing values")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    only_types = [t.strip() for t in args.only_types.split(",") if t.strip()] or None
    write_failures = Path(args.write_failures) if args.write_failures.strip() else None

    raise SystemExit(
        run(
            only_types=only_types,
            only_missing_primary=bool(args.only_missing_primary),
            max_failures=int(args.max_failures),
            write_failures=write_failures,
            force_overwrite=bool(args.force_overwrite),
            dry_run=bool(args.dry_run),
        )
    )


if __name__ == "__main__":
    main()
