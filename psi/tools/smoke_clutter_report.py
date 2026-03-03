from __future__ import annotations

import sqlite3
from pathlib import Path


def _default_db_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return Path(__import__("os").environ.get("PSI_DB_PATH", str(root / "psi" / "psi.sqlite"))).expanduser().resolve()


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(r[0]) for r in rows]


def _text_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    cols: list[str] = []
    for r in rows:
        name = str(r[1] or "")
        typ = str(r[2] or "").upper()
        if ("CHAR" in typ) or ("TEXT" in typ) or (typ == ""):
            cols.append(name)
    return sorted(cols)


def build_report(db_path: Path, *, sample_limit: int = 200) -> str:
    markers = ("di_contract_smoke", "smoke", "synthetic")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = _table_names(conn)
        lines: list[str] = []
        lines.append("# Smoke Clutter Report")
        lines.append("")
        lines.append(f"- db_path: `{db_path}`")
        lines.append(f"- sample_limit: `{int(sample_limit)}`")
        lines.append("")
        lines.append("## Table Activity")
        lines.append("")
        active_tables = [
            "decision_snapshots",
            "data_records",
            "evidence",
            "report_runs",
            "measurement_qc",
            "data_measurements",
            "audit_events",
        ]
        for t in sorted([x for x in active_tables if x in tables]):
            n = conn.execute(f"SELECT COUNT(1) FROM {t}").fetchone()[0]
            lines.append(f"- `{t}`: {int(n)} rows")
        lines.append("")
        lines.append("## Marker Matches")
        lines.append("")
        findings: list[tuple[str, str, int, str]] = []
        for t in sorted(tables):
            text_cols = _text_columns(conn, t)
            if not text_cols:
                continue
            for c in text_cols:
                col_l = c.lower()
                if not any(x in col_l for x in ("note", "source", "run", "prov", "created_by", "summary", "details", "title", "path")):
                    continue
                where = " OR ".join([f"LOWER(COALESCE({c}, '')) LIKE ?" for _ in markers])
                params = [f"%{m}%" for m in markers]
                rows = conn.execute(
                    f"SELECT rowid AS __rid, {c} AS val FROM {t} WHERE {where} ORDER BY rowid DESC LIMIT ?",
                    [*params, int(sample_limit)],
                ).fetchall()
                for r in rows:
                    snippet = str(r["val"] or "").strip().replace("\n", " ")
                    if len(snippet) > 120:
                        snippet = snippet[:117] + "..."
                    findings.append((t, c, int(r["__rid"]), snippet))
        if not findings:
            lines.append("No marker matches found for `di_contract_smoke` / `smoke` / `synthetic` in scanned text columns.")
        else:
            lines.append("| table | column | rowid | snippet |")
            lines.append("|---|---|---:|---|")
            for t, c, rid, snip in sorted(findings, key=lambda x: (x[0], x[1], -x[2], x[3])):
                lines.append(f"| `{t}` | `{c}` | {rid} | `{snip}` |")
        lines.append("")
        return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    db_path = _default_db_path()
    report = build_report(db_path)
    out_dir = root / "_artifacts" / "smoke_clutter_report"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "SMOKE_CLUTTER_REPORT.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"smoke_clutter_report: db_path={db_path}")
    print(f"smoke_clutter_report: report={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
