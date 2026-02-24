from __future__ import annotations

import datetime as _dt
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
