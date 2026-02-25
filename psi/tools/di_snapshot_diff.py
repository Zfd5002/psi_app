"""DI DecisionSnapshot diff + drift diagnostics (analytical only).

Run:
  python -m psi.tools.di_snapshot_diff --id1 <snapshot_id> --id2 <snapshot_id>

Notes:
- Read-only: does not mutate the DB.
- Deterministic: output ordering is stable; no timestamps.
- Derived-only: drift labels are computed only from signals already embedded in snapshots.

This tool is intended for Roadmap v0.2 diff/diagnostics only.
"""

from __future__ import annotations

import argparse
from typing import List, Optional

from psi.core.db import DB_PATH, get_db

from psi.services.di.util import stable_json_dumps
from psi.services.di.snapshot_diff import DriftResult, compute_snapshot_diff_by_id


# -----------------------------
# DB helpers
# -----------------------------

def _default_db_path() -> str:
    # Shared with web app via psi.core.db (respects PSI_DB_PATH)
    return str(DB_PATH)


"""NOTE: DI snapshot diff logic lives in `psi.services.di.snapshot_diff`.

This CLI module is intentionally a thin wrapper so diff algorithms are not duplicated between
CLI and web.
"""


# -----------------------------
# Rendering
# -----------------------------


def _render_text(res: DriftResult, *, id1: int, id2: int) -> str:
    lines: List[str] = []
    lines.append("DI SNAPSHOT DIFF")
    lines.append(f"id1={id1}  id2={id2}")
    lines.append("")

    s = res.summary
    lines.append("SUMMARY")
    lines.append(f"- drift_label: {res.drift_label}")
    lines.append(f"- policy_semantics_hash: {s['policy_semantics_hash']['id1']} -> {s['policy_semantics_hash']['id2']}")
    lines.append(f"- policy_package_hash:   {s['policy_package_hash']['id1']} -> {s['policy_package_hash']['id2']}")
    lines.append(f"- catalog_hash:          {s['catalog_hash']['id1']} -> {s['catalog_hash']['id2']}")
    lines.append(f"- coverage_fingerprint:  {s['coverage_fingerprint']['id1']} -> {s['coverage_fingerprint']['id2']}")
    lines.append(f"- qc_mode:               {s['qc_mode']['id1']} -> {s['qc_mode']['id2']}")
    lines.append(f"- selection_semantics:   {s['selection_semantics_version']['id1']} -> {s['selection_semantics_version']['id2']}")
    lines.append("")

    if not res.changes:
        lines.append("DETAIL")
        lines.append("- no changes")
        return "\n".join(lines) + "\n"

    lines.append("DETAIL")

    def _emit_section(title: str) -> None:
        lines.append("")
        lines.append(title)

    # Deterministic section order
    for section in ("hashes", "identifiers", "readiness", "gate_outcomes", "measurement_ids_used"):
        if section not in res.changes:
            continue
        _emit_section(section)
        payload = res.changes[section]

        if section in ("hashes", "identifiers"):
            for k in sorted(payload.keys()):
                v = payload[k]
                if isinstance(v, dict) and "from" in v and "to" in v:
                    lines.append(f"- {k}: {v['from']} -> {v['to']}")
                else:
                    lines.append(f"- {k}: {stable_json_dumps(v)}")
            continue

        if section == "measurement_ids_used":
            rem = payload.get("removed") or []
            add = payload.get("added") or []
            lines.append(f"- removed: {stable_json_dumps(rem)}")
            lines.append(f"- added:   {stable_json_dumps(add)}")
            continue

        if section == "readiness":
            for k in sorted(payload.keys()):
                v = payload[k]
                if k == "blockers":
                    rem = v.get("removed") or []
                    add = v.get("added") or []
                    lines.append(f"- blockers_removed: {stable_json_dumps(rem)}")
                    lines.append(f"- blockers_added:   {stable_json_dumps(add)}")
                elif isinstance(v, dict) and "from" in v and "to" in v:
                    lines.append(f"- {k}: {v['from']} -> {v['to']}")
                else:
                    lines.append(f"- {k}: {stable_json_dumps(v)}")
            continue

        if section == "gate_outcomes":
            for gk in sorted(payload.keys()):
                gi = payload[gk]
                lines.append(f"- {gk}:")
                # deterministically ordered gate fields
                if isinstance(gi, dict) and ("added" in gi or "removed" in gi):
                    if "added" in gi:
                        lines.append(f"    + added: {stable_json_dumps(gi['added'])}")
                    if "removed" in gi:
                        lines.append(f"    - removed: {stable_json_dumps(gi['removed'])}")
                    continue
                for kk in sorted(gi.keys()):
                    vv = gi[kk]
                    if isinstance(vv, dict) and "from" in vv and "to" in vv:
                        lines.append(f"    ~ {kk}: {vv['from']} -> {vv['to']}")
                    elif isinstance(vv, dict) and ("removed" in vv or "added" in vv):
                        lines.append(f"    ~ {kk}: removed={stable_json_dumps(vv.get('removed') or [])} added={stable_json_dumps(vv.get('added') or [])}")
                    else:
                        lines.append(f"    ~ {kk}: {stable_json_dumps(vv)}")

    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="DI DecisionSnapshot diff (analytical, deterministic)")
    p.add_argument("--id1", required=True, type=int, help="DecisionSnapshot id (first)")
    p.add_argument("--id2", required=True, type=int, help="DecisionSnapshot id (second)")
    p.add_argument("--db", default=_default_db_path(), help="Path to PSI sqlite DB (default: PSI_DB_PATH or psi/psi.sqlite)")
    p.add_argument("--format", default="text", choices=("text", "json"), help="Output format")

    args = p.parse_args(argv)

    with get_db(args.db.strip() or None, ensure=True) as db:
        res = compute_snapshot_diff_by_id(db=db, id1=int(args.id1), id2=int(args.id2))

    if args.format == "json":
        payload = {
            "drift_label": res.drift_label,
            "summary": res.summary,
            "changes": res.changes,
        }
        print(stable_json_dumps(payload))
    else:
        print(_render_text(res, id1=int(args.id1), id2=int(args.id2)), end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
