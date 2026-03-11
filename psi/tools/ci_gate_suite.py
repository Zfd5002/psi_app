from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


GATES: list[list[str]] = [
    [sys.executable, "-m", "compileall", "-q", "psi"],
    [sys.executable, "-m", "psi.tools.db_schema_sanity"],
    [sys.executable, "-m", "psi.tools.di_contract_smoke"],
    [sys.executable, "-m", "psi.tools.di_replay_regression", "--limit", "5"],
]


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    if stdout:
        sys.stdout.write(stdout)
        if not stdout.endswith("\n"):
            sys.stdout.write("\n")
    if stderr:
        sys.stderr.write(stderr)
        if not stderr.endswith("\n"):
            sys.stderr.write("\n")
    return {
        "cmd": cmd,
        "returncode": int(proc.returncode),
        "ok": proc.returncode == 0,
    }


def main() -> int:
    results: list[dict[str, Any]] = []
    failed = False
    for cmd in GATES:
        res = _run(cmd)
        results.append(res)
        if not res["ok"]:
            failed = True
            break

    summary = {
        "ci_gate_suite_v1": {
            "failed": failed,
            "results": results,
        }
    }
    print(json.dumps(summary, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
