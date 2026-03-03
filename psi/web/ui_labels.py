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
    "nod": "NOD",
    "spr": "SPR",
    "sec": "SEC",
    "lal": "LAL",
    "hmw": "HMW",
    "lmw": "LMW",
    "fc": "Fc",
    "igg": "IgG",
    "hek": "HEK",
    "noncomp": "NONCOMP",
}


_STATE_OVERRIDES = {
    "not_assessed": "Not assessed by this surface.",
}


def _humanize_word(word: str) -> str:
    low = word.lower()
    if low in _ACRONYMS:
        return _ACRONYMS[low]
    if word.isdigit():
        return word
    return low.capitalize()


def humanize_slug_or_token(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower() == "pk_pd":
        return "PK/PD"
    parts = [p for p in re.split(r"[_\s]+", raw) if p]
    return " ".join(_humanize_word(p) for p in parts)


def humanize_key(key: str) -> str:
    raw = str(key or "").strip()
    if not raw:
        return ""
    override = _KEY_OVERRIDES.get(raw)
    if override:
        return override
    return humanize_slug_or_token(raw)


def humanize_state(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    override = _STATE_OVERRIDES.get(raw.lower())
    if override:
        return override
    return humanize_slug_or_token(raw)


def humanize_path_token(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    segments = [seg for seg in raw.split("/") if seg != ""]
    if not segments:
        return ""
    return " / ".join(humanize_slug_or_token(seg) for seg in segments)
