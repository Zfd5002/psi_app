from __future__ import annotations
"""DEPRECATED COMPAT SHIM.

`psi.services.v3_board_reports` is not router-wired in V3 runtime surfaces.
Live report routes use `psi.services.report_engine` + `psi.services.v3_narrative`.
This shim remains only for historical import compatibility.
"""

from psi.services._deprecated.v3_board_reports import *  # noqa: F401,F403

