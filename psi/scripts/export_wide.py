"""
Export PSI measurements in a deterministic wide/pivot CSV format.

Usage:
  python -m psi.scripts.export_wide --db ./psi/psi.sqlite --out /tmp/psi_wide.csv
  python -m psi.scripts.export_wide --db ./psi/psi.sqlite --out /tmp/psi_wide.csv --include-extras
"""

from __future__ import annotations

import argparse
from pathlib import Path

from psi.core.db import get_db
from psi.services.export_wide import export_wide_csv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to SQLite DB file (e.g., ./psi/psi.sqlite)")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--include-extras", action="store_true", help="Include unregistered measurement keys as extras__* columns")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    if not db_path.exists():
        raise SystemExit(f"--db not found: {db_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db(str(db_path)) as db:
        export_wide_csv(db, out_path=str(out_path), include_extras=bool(args.include_extras))

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

