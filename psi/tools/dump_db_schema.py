"""
Dump SQLite schema (tables + PRAGMA table_info) to a markdown file.

Usage:
  python -m psi.tools.dump_db_schema --db ./psi/psi.sqlite --out ./docs/DB_SCHEMA.md
  python -m psi.tools.dump_db_schema
"""
from __future__ import annotations

import argparse
import sqlite3
import tempfile
from pathlib import Path


HEADER = """# PSI SQLite DB Schema Reference

This file exists because PSI overlays intentionally exclude `psi/psi.sqlite` and any other `.sqlite` files.
When debugging or extending PSI, it is still critical to know the **current** DB structure.

## How this file is produced

Generate (or refresh) this document from your local DB:

```bash
(.venv) python -m psi.tools.dump_db_schema --db ./psi/psi.sqlite --out ./docs/DB_SCHEMA.md
```

Commit the updated `docs/DB_SCHEMA.md` alongside any schema/migration changes.

## Notes

- This is **not** a migration log; it is a compact “what tables/columns exist right now” reference.
- If a table/column is renamed, this document should change in the same patch.

## Schema Snapshot (Generated)

<!-- BEGIN AUTO-GENERATED DB SCHEMA -->
"""

FOOTER = """<!-- END AUTO-GENERATED DB SCHEMA -->
"""


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
    ).fetchall()
    return [r[0] for r in rows]


def _table_info(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return [
        {
            "cid": r[0],
            "name": r[1],
            "type": r[2],
            "notnull": bool(r[3]),
            "default": r[4],
            "pk": bool(r[5]),
        }
        for r in rows
    ]


def _render_generated_block(db_path: Path, tables: dict[str, list[dict]]) -> str:
    out: list[str] = []
    out.append(f"_Source DB: `{db_path}`_\n\n")
    out.append("### Tables\n\n")
    for name in sorted(tables.keys()):
        out.append(f"#### {name}\n\n")
        out.append("| cid | name | type | notnull | default | pk |\n")
        out.append("| ---: | --- | --- | :---: | --- | :---: |\n")
        for c in tables[name]:
            default_val = "" if c["default"] is None else str(c["default"])
            out.append(
                f"| {c['cid']} | {c['name']} | {c['type']} | {('Y' if c['notnull'] else '')} | {default_val} | {('Y' if c['pk'] else '')} |\n"
            )
        out.append("\n")
    return "".join(out)


def _render_md(db_path: Path, tables: dict[str, list[dict]]) -> str:
    return HEADER + _render_generated_block(db_path, tables) + FOOTER


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(repo_root / "psi" / "psi.sqlite"), help="Path to SQLite db, e.g. ./psi/psi.sqlite")
    ap.add_argument("--out", default=str(repo_root / "docs" / "DB_SCHEMA.md"), help="Output markdown path, e.g. ./docs/DB_SCHEMA.md")
    args = ap.parse_args()

    db_path = Path(args.db).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        tables = {t: _table_info(conn, t) for t in _list_tables(conn)}
    finally:
        conn.close()

    _atomic_write_text(out_path, _render_md(db_path, tables))
    print(f"Wrote schema to: {out_path} (tables={len(tables)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
