from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TARGETS = [
    "psi/services/molecules.py",
    "psi/services/molecule_header.py",
    "psi/services/molecule_sequences.py",
    "psi/services/molecule_viewer.py",
    "psi/services/di/runner.py",
    "psi/services/di/compute.py",
    "psi/services/di/soe.py",
    "psi/tools/di_contract_smoke.py",
]


def _count_loc(lines: list[str]) -> int:
    count = 0
    for line in lines:
        if line.strip():
            count += 1
    return count


def main() -> int:
    rows: list[dict[str, object]] = []
    for rel in TARGETS:
        path = ROOT / rel
        if path.exists():
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            rows.append(
                {
                    "path": rel,
                    "exists": True,
                    "lines": len(lines),
                    "loc_nonblank": _count_loc(lines),
                    "bytes": path.stat().st_size,
                }
            )
        else:
            rows.append(
                {
                    "path": rel,
                    "exists": False,
                    "lines": 0,
                    "loc_nonblank": 0,
                    "bytes": 0,
                }
            )
    print(json.dumps({"code_size_report_v1": rows}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
