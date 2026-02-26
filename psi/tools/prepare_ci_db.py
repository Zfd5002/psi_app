from __future__ import annotations

"""Prepare an ephemeral SQLite DB for CI/local smoke tooling.

This tool is tooling-only. It creates/initializes a SQLite DB with the current
schema so DB-dependent smoke checks do not rely on a checked-in runtime DB.
"""

import argparse
import os
from pathlib import Path

from sqlalchemy import create_engine

from psi.core.db import ensure_schema


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m psi.tools.prepare_ci_db")
    ap.add_argument("--db", required=True, help="Path to ephemeral sqlite database file")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{db_path}", future=True)
    try:
        ensure_schema(engine_override=eng)
    finally:
        eng.dispose()

    # Print a deterministic export hint for shell use in CI.
    print(str(db_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

