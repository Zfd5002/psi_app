"""
Export PSI measurements in a deterministic wide/pivot CSV format.

Usage:
  python -m psi.scripts.export_wide --db ./psi/psi.sqlite --out /tmp/psi_wide.csv
  python -m psi.scripts.export_wide --db ./psi/psi.sqlite --out /tmp/psi_wide.csv --include-extras
"""

from __future__ import annotations

import argparse
import datetime
from pathlib import Path

from psi.core.db import get_db
from psi.services.export_wide import ExportWideOptions, export_wide_to_csv
from psi.core.export_profiles import list_profiles


def _parse_as_of(s: str | None) -> datetime.datetime | None:
    if not s:
        return None
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(t)
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to SQLite DB file (e.g., ./psi/psi.sqlite)")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--include-extras", action="store_true", help="Include unregistered measurement keys as extras__* columns")
    ap.add_argument(
        "--profile",
        default=None,
        help=f"Named export profile (optional). Available: {', '.join(list_profiles())}",
    )
    ap.add_argument(
        "--qc-mode",
        default=None,
        choices=["none", "model_safe", "strict"],
        help="QC filtering mode for measurement selection. If omitted and --profile is set, the profile default applies.",
    )
    ap.add_argument("--as-of", default=None, help="ISO8601 timestamp. If set, export is leakage-safe as-of this time (e.g., 2026-02-01T00:00:00)")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    if not db_path.exists():
        raise SystemExit(f"--db not found: {db_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db(str(db_path)) as db:
        opts = ExportWideOptions(
            include_extras=bool(args.include_extras),
            as_of_ts=_parse_as_of(args.as_of),
            qc_mode=(str(args.qc_mode).strip() if args.qc_mode is not None else None),
            profile=(str(args.profile).strip() if args.profile else None),
        )
        export_wide_to_csv(db, out_path=str(out_path), options=opts)

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()

