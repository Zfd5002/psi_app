from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psi.core.db import get_db
from psi.core.di.policy import load_policy
from psi.core.models import DecisionSnapshot
from psi.services.di import verify as verify_mod


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_registry_manifest() -> dict[str, Any]:
    p = _repo_root() / "psi" / "core" / "di" / "policy_registry_manifest.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _current_policy_hash_rows() -> list[dict[str, str]]:
    pdir = _repo_root() / "psi" / "core" / "di" / "policies"
    rows: list[dict[str, str]] = []
    for p in sorted(pdir.glob("*.json")):
        pol = load_policy(p)
        rows.append(
            {
                "filename": p.name,
                "policy_id": str(pol.policy_id or ""),
                "policy_version": str(pol.version or ""),
                "policy_package_hash": str(pol.policy_package_hash or ""),
                "policy_semantics_hash": str(pol.policy_semantics_hash or ""),
            }
        )
    return rows


def _extract_snapshot_hashes(snap: DecisionSnapshot) -> dict[str, str]:
    inp = verify_mod._parse_json_field(snap.inputs_json, default={})
    out = verify_mod._parse_json_field(snap.outputs_json, default={})
    sem = ""
    pkg = ""
    if isinstance(out, dict):
        prov = out.get("provenance")
        if isinstance(prov, dict):
            pref = prov.get("policy_ref")
            if isinstance(pref, dict):
                sem = str(pref.get("policy_semantics_hash") or "").strip() or sem
                pkg = str(pref.get("policy_package_hash") or "").strip() or pkg
        pol = out.get("policy")
        if isinstance(pol, dict):
            sem = str(pol.get("hash") or "").strip() or sem
            pkg = str(pol.get("policy_package_hash") or "").strip() or pkg
    if isinstance(inp, dict):
        sem = str(inp.get("policy_hash") or "").strip() or sem
        pkg = str(inp.get("policy_package_hash") or "").strip() or pkg
    return {"policy_semantics_hash": sem, "policy_package_hash": pkg}


def _snapshot_referenced_hash_rows(*, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with get_db(None, ensure=False) as db:
        q = db.query(DecisionSnapshot).order_by(DecisionSnapshot.id.asc())
        if limit is not None:
            q = q.limit(int(limit))
        for s in q.all():
            hs = _extract_snapshot_hashes(s)
            rows.append(
                {
                    "snapshot_id": int(s.id),
                    "decision_key": str(s.decision_key or ""),
                    "policy_package_hash": str(hs.get("policy_package_hash") or ""),
                    "policy_semantics_hash": str(hs.get("policy_semantics_hash") or ""),
                }
            )
    return rows


def build_policy_hash_audit_report(*, snapshot_limit: int | None = None) -> dict[str, Any]:
    current = _current_policy_hash_rows()
    registry = _load_registry_manifest()
    reg_entries = registry.get("entries") if isinstance(registry, dict) else []
    registry_pkg_hashes = {str((e or {}).get("policy_package_hash") or "") for e in reg_entries if isinstance(e, dict)}
    snap_rows = _snapshot_referenced_hash_rows(limit=snapshot_limit)

    snapshot_hashes = sorted({str(r.get("policy_package_hash") or "") for r in snap_rows if str(r.get("policy_package_hash") or "")})
    current_hashes = sorted({str(r.get("policy_package_hash") or "") for r in current if str(r.get("policy_package_hash") or "")})
    mismatches = {
        "snapshot_package_hashes_missing_in_registry": [h for h in snapshot_hashes if h not in registry_pkg_hashes],
        "registry_package_hashes_missing_in_current_files": [str((e or {}).get("policy_package_hash") or "") for e in reg_entries if isinstance(e, dict) and str((e or {}).get("policy_package_hash") or "") not in current_hashes],
    }
    return {
        "policy_hash_audit_v1": {
            "current_policy_hashes": current,
            "registry_manifest_entries": reg_entries if isinstance(reg_entries, list) else [],
            "snapshot_referenced_hashes": snap_rows,
            "mismatch_report": mismatches,
        }
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m psi.tools.policy_hash_audit")
    ap.add_argument("--snapshot-limit", type=int, default=None, help="Optional snapshot rows limit (default all)")
    args = ap.parse_args()
    report = build_policy_hash_audit_report(snapshot_limit=args.snapshot_limit)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
