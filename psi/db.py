"""Backward-compatible re-export.

The production architecture lives under :mod:`psi.core`.
This module remains to avoid breaking older import paths.
"""

from .core.db import *  # noqa: F401,F403
