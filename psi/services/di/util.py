from __future__ import annotations

import datetime as _dt
import os
from typing import Any, Optional

from psi.core.utils import stable_json_dumps


def parse_iso(ts: Optional[str]) -> Optional[_dt.datetime]:
    if not ts:
        return None
    s = str(ts).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = _dt.datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(_dt.timezone.utc).replace(tzinfo=None)
    return dt


def qc_status_from_flag(raw: Any) -> str:
    # Back-compat: older tooling uses qc_flag like a boolean "flagged".
    if raw in (None, "", 0, "0"):
        return "unreviewed"
    s = str(raw).strip().lower()
    if s in ("approved", "pass", "ok"):
        return "approved"
    if s in ("rejected", "fail", "bad", "flagged", "1", "true"):
        return "rejected"
    if s in ("quarantined", "quarantine"):
        return "quarantined"
    return "unknown"


def value_functions_enforcement_reason(
    *,
    applicable: bool,
    policy_flag_enabled: bool,
    evaluator_version_expected: str | None,
    evaluator_version_actual: str | None,
) -> str:
    """Deterministic reason string for value-function enforcement state.

    Allowed values:
    - active
    - policy_flag_off
    - evaluator_version_mismatch
    - not_applicable
    """
    if not applicable:
        return "not_applicable"
    if not bool(policy_flag_enabled):
        return "policy_flag_off"
    ev_expected = str(evaluator_version_expected or "").strip()
    ev_actual = str(evaluator_version_actual or "").strip()
    if not ev_expected or not ev_actual:
        return "not_applicable"
    if ev_expected != ev_actual:
        return "evaluator_version_mismatch"
    return "active"


def is_heavy_compute_enabled() -> bool:
    """Global heavy-compute toggle (UI/runtime convenience only; default OFF)."""
    return str(os.getenv("PSI_HEAVY_COMPUTE", "0") or "0").strip() == "1"


def heavy_compute_banner_text(*, enabled: bool) -> str:
    if bool(enabled):
        return "Heavy Compute: ON (PSI_HEAVY_COMPUTE=1). Does not affect DI snapshot hashes."
    return "Heavy Compute: OFF (default, PSI_HEAVY_COMPUTE=0). Does not affect DI snapshot hashes."
