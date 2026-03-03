from __future__ import annotations

import json
from typing import Any


def safe_json_dict(raw: str | None) -> dict[str, Any]:
    """Decode JSON string to dict with deterministic empty-object fallback."""
    try:
        obj = json.loads(raw or "{}")
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}
