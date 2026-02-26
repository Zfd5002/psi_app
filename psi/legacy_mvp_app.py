"""Archived legacy MVP app shim (not part of PSI runtime).

The pre-DI Flask-style MVP app has been archived to:
  docs/legacy/legacy_mvp_app.py

This module remains only as an overlay-safe tombstone so accidental imports fail
with a clear message instead of silently reviving an unsupported runtime path.
"""

from __future__ import annotations


_ARCHIVE_MSG = (
    "psi.legacy_mvp_app is archived and not part of the supported PSI runtime. "
    "Use psi.web.app / ASGI routes for the current UI, or inspect docs/legacy/legacy_mvp_app.py "
    "for historical reference."
)


def __getattr__(name: str):  # pragma: no cover - defensive compatibility shim
    raise RuntimeError(_ARCHIVE_MSG)

