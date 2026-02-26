from __future__ import annotations

import importlib.util
import subprocess
import sys


def main() -> int:
    if importlib.util.find_spec("pytest") is None:
        print("SKIP pytest_smoke: pytest not installed")
        return 0
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"])
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
