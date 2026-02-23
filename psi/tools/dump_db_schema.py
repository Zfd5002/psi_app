"""
Dump SQLite schema (tables + PRAGMA table_info) to a markdown file.

Usage:
  python -m psi.tools.dump_db_schema --db ./psi/psi.sqlite --out ./docs/DB_SCHEMA.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sqlite3
from pathlib import Path


def _list_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"
    ).fetchall()
    return [r[0] for r in rows]


def _table_info(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    # cid, name, type, notnull, dflt_value, pk
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


def _render_md(db_path: Path, tables: dict[str, list[dict]]) -> str:
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    out = []
    out.append("# PSI SQLite DB Schema Reference\n")
    out.append(f"_Generated from `{db_path}` at `{ts}`._\n")
    out.append("## Tables\n")
    for name in sorted(tables.keys()):
        out.append(f"### {name}\n")
        out.append("| cid | name | type | notnull | default | pk |\n")
        out.append("| ---:| --- | --- | :---: | --- | :---: |\n")
        for c in tables[name]:
            out.append(
                f"| {c['cid']} | {c['name']} | {c['type']} | {('Y' if c['notnull'] else '')} | {c['default'] if c['default'] is not None else ''} | {('Y' if c['pk'] else '')} |\n"
            )
        out.append("\n")
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to SQLite db, e.g. ./psi/psi.sqlite")
    ap.add_argument("--out", required=True, help="Output markdown path, e.g. ./docs/DB_SCHEMA.md")
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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render_md(db_path, tables), encoding="utf-8")
    print(f"Wrote schema to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
