from __future__ import annotations

import re

_KEY_OVERRIDES = {
    "as_of_ts": "As Of",
    "qc_mode": "QC Mode",
    "run_semantics": "Run Semantics",
    "value_functions_enforced": "Value Functions Enforced",
    "value_functions_enforcement_reason": "Value Functions Enforcement Reason",
}

_ACRONYMS = {
    "qc": "QC",
    "di": "DI",
    "id": "ID",
    "api": "API",
    "url": "URL",
    "json": "JSON",
    "sql": "SQL",
    "pk": "PK",
    "pd": "PD",
    "mabel": "MABEL",
    "noael": "NOAEL",
}


def humanize_key(key: str) -> str:
    raw = str(key or "").strip()
    if not raw:
        return ""
    override = _KEY_OVERRIDES.get(raw)
    if override:
        return override
    parts = [p for p in re.split(r"[_\s]+", raw) if p]
    out: list[str] = []
    for p in parts:
        low = p.lower()
        if low in _ACRONYMS:
            out.append(_ACRONYMS[low])
        elif p.isdigit():
            out.append(p)
        else:
            out.append(low.capitalize())
    return " ".join(out)
