from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    p = path or (_repo_root() / "psi" / "core" / "di" / "policy_immutability_manifest.json")
    return json.loads(p.read_text(encoding="utf-8"))


def validate_policy_immutability() -> dict[str, Any]:
    root = _repo_root()
    manifest = load_manifest()
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list):
        raise ValueError("Invalid immutability manifest: files list missing")

    mismatches: list[dict[str, str]] = []
    missing: list[str] = []
    for rec in files:
        if not isinstance(rec, dict):
            continue
        rel = str(rec.get("path") or "").strip()
        want = str(rec.get("sha256") or "").strip().lower()
        if not rel or not want:
            continue
        p = root / rel
        if not p.exists():
            missing.append(rel)
            continue
        got = _sha256(p)
        if got != want:
            mismatches.append({"path": rel, "expected_sha256": want, "actual_sha256": got})

    return {
        "ok": not missing and not mismatches,
        "missing": missing,
        "mismatches": mismatches,
        "checked": len(files),
        "manifest_version": str(manifest.get("manifest_version") or ""),
    }


def main() -> int:
    try:
        report = validate_policy_immutability()
    except Exception as e:
        print(f"policy_immutability_check FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    if not report["ok"]:
        print(json.dumps({"policy_immutability_check": report}, sort_keys=True), file=sys.stderr)
        return 2
    print(f"PASS policy_immutability_check: checked={report['checked']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
