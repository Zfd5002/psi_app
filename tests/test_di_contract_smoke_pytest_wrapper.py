from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine

from psi.core.db import ensure_schema


def test_di_contract_smoke_cli_wrapper():
    env = None
    tmpdir = None
    if "PSI_DB_PATH" not in os.environ:
        tmpdir = tempfile.TemporaryDirectory(prefix="psi_pytest_smoke_db_", dir=tempfile.gettempdir())
        db_path = Path(tmpdir.name) / "pytest_contract_smoke.sqlite"
        eng = create_engine(f"sqlite:///{db_path}", future=True)
        try:
            ensure_schema(engine_override=eng)
        finally:
            eng.dispose()
        env = dict(os.environ)
        env["PSI_DB_PATH"] = str(db_path)
    proc = subprocess.run(
        [sys.executable, "-m", "psi.tools.di_contract_smoke"],
        capture_output=True,
        text=True,
        env=env,
    )
    if tmpdir is not None:
        tmpdir.cleanup()
    assert proc.returncode == 0, (
        "di_contract_smoke failed via pytest wrapper\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}\n"
    )
