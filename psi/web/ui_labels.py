from __future__ import annotations

import re

_KEY_OVERRIDES = {
    "as_of_ts": "As Of",
    "qc_mode": "QC Mode",
    "run_semantics": "Run Semantics",
    "value_functions_enforced": "Value Functions Enforced",
    "value_functions_enforcement_reason": "Value Functions Enforcement Reason",
    "advance_to_in_vivo": "Development Progression",
    "ready_for_scaleup_screen": "Scale-Up Readiness Screen",
    "development_progression_v1": "Development Progression v1",
    "g1_material_readiness": "Gate 1: Material Readiness",
    "g2_purity_integrity": "Gate 2: Quality / Integrity",
    "g3_endotoxin": "Gate 3: Endotoxin Control",
    "g3_stability": "Gate 3: Stability",
    "g4_functional": "Gate 4: Functional Evidence",
    "g5_internalization_if_kd_present": "Gate 5: Modality-Specific Requirements",
    "g6_pk_optional": "Gate 6: In Vivo Readiness",
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
    if not override:
        override = _KEY_OVERRIDES.get(raw.lower())
    if override:
        return override
    return humanize_slug_or_token(raw)


def humanize_decision_key(key: str) -> str:
    """Scientist-facing display label for DI decision identifiers."""
    return humanize_key(key)


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
