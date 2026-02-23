from __future__ import annotations


import sqlite3
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine

from psi.core import db as db_mod


def _load_model_columns() -> dict[str, set[str]]:
    """
    Load table → column mappings from SQLAlchemy metadata.

    This represents the true declared schema in psi.core.models.
    """
    from psi.core.models import Base

    model_columns: dict[str, set[str]] = {}

    # Use sorted_tables for deterministic ordering
    for table in Base.metadata.sorted_tables:
        model_columns[table.name] = {col.name for col in table.columns}

    return model_columns


def _pragma_columns(sqlite_path: Path, table: str) -> set[str]:
    with sqlite3.connect(sqlite_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def main() -> int:
    model_columns = _load_model_columns()
    failures: list[tuple[str, list[str], list[str], bool]] = []
    warnings = 0

    with tempfile.TemporaryDirectory(prefix="psi_db_schema_sanity_", dir="/tmp") as tmpdir:
        sqlite_path = Path(tmpdir) / "schema_sanity.sqlite"
        eng = create_engine(f"sqlite:///{sqlite_path}", future=True)
        try:
            db_mod.ensure_schema(engine_override=eng)
        finally:
            eng.dispose()

        for table, expected_cols in sorted(model_columns.items()):
            expected = set(expected_cols)
            actual = _pragma_columns(sqlite_path, table)
            missing = sorted(expected - actual)
            extras = sorted(actual - expected)
            table_missing = not actual
            if missing or table_missing:
                failures.append((table, missing, extras, table_missing))
            elif extras:
                warnings += 1
                print(f"WARN table={table} extra_columns={extras}")

    if failures:
        print("FAIL db_schema_sanity: model_columns drift detected", file=sys.stderr)
        for table, missing, extras, table_missing in failures:
            if table_missing:
                print(f"  table={table} error=table_missing_or_empty_pragma", file=sys.stderr)
            if missing:
                print(f"  table={table} missing_columns={missing}", file=sys.stderr)
            if extras:
                print(f"  table={table} extra_columns={extras}", file=sys.stderr)
        return 1

    print(
        "PASS db_schema_sanity: "
        f"tables_checked={len(model_columns)} warnings_extra_columns={warnings}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
