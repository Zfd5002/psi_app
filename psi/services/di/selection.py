"""DI selection facade.

This module exists to keep `runner.py` small and to provide a stable import surface
for selection semantics as DI evolves.

Hard rule: deterministic ordering and stable ignore taxonomy.
"""

from __future__ import annotations

from psi.services.di.selectors import ALLOWED_IGNORE_REASON_KEYS, select_batch_measurements

__all__ = ["select_batch_measurements", "ALLOWED_IGNORE_REASON_KEYS"]
