from __future__ import annotations

import importlib
import os
from typing import Iterable

from fastapi import FastAPI


def _parse_enabled() -> list[str]:
    raw = os.getenv("PSI_EXTENSIONS", "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def load_extensions(app: FastAPI) -> list[str]:
    """Load enabled extensions.

    Extensions are regular Python packages under `psi.extensions.<name>`.
    To enable, set `PSI_EXTENSIONS=cmc,eln`.

    Each extension may implement:
      - `init_extension(app: FastAPI) -> None`

    Extensions can also import and call core registry helpers at import time.
    """

    enabled = _parse_enabled()
    # Auto-load structure extension when heavy compute is enabled globally.
    if os.getenv("PSI_ENABLE_HEAVY_COMPUTE", "").strip() == "1" and "structure" not in enabled:
        enabled = enabled + ["structure"]
    loaded: list[str] = []
    for name in enabled:
        mod_name = f"psi.extensions.{name}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception:
            continue
        init_fn = getattr(mod, "init_extension", None)
        if callable(init_fn):
            try:
                init_fn(app)
            except TypeError:
                init_fn()
        loaded.append(name)
    app.state.enabled_extensions = loaded
    return loaded
