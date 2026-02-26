from __future__ import annotations

import subprocess
import sys


def test_di_contract_smoke_cli_wrapper():
    proc = subprocess.run(
        [sys.executable, "-m", "psi.tools.di_contract_smoke"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "di_contract_smoke failed via pytest wrapper\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}\n"
    )
