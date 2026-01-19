"""Backward-compatible ASGI entrypoint.

Prefer running `psi.web.asgi:app` going forward.
"""

from psi.web.asgi import app  # noqa: F401
