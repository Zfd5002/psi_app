"""Assay schema registry + normalization helpers.

PSI v1.2.1
- Provide a stable place to define assay buckets and human-readable result summaries.
- Goal is to add new assays by editing this file (and optionally adding parsing rules),
  without template surgery.

Notes
- DataRecord stores results in results_json (and sometimes derived_outputs_json / primary_result_text in newer flows).
- We normalize at read-time (no DB migration required).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


def _loads(s: str | None) -> dict[str, Any]:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


@dataclass(frozen=True)
class AssayDef:
    key: str
    display_name: str
    match: Callable[[Any], bool]
    summarize: Callable[[Any], str]


def _is_sec(r: Any) -> bool:
    return getattr(r, "data_type", None) == "CMC_Analytics" and getattr(r, "method", None) in ("SEC_HPLC", "SEC")


def _is_endotoxin(r: Any) -> bool:
    return getattr(r, "data_type", None) == "CMC_Analytics" and getattr(r, "method", None) == "Endotoxin"


def _is_binding(r: Any) -> bool:
    return getattr(r, "data_type", None) == "Binding" and getattr(r, "method", None) in ("BLI", "SPR")


def _fmt_pct(x: Any) -> str:
    try:
        xf = float(x)
        return f"{xf:.0f}%" if abs(xf - round(xf)) < 1e-9 else f"{xf:.1f}%"
    except Exception:
        return f"{x}%" if x is not None else "n/a"


def _summarize_sec(r: Any) -> str:
    # Prefer explicit text if present.
    prt = getattr(r, "primary_result_text", None)
    if prt:
        return str(prt)

    out = _loads(getattr(r, "derived_outputs_json", None)) or _loads(getattr(r, "results_json", None))
    mon = out.get("monomer_pct")
    hmw = out.get("hmw_pct")
    lmw = out.get("lmw_pct")

    if mon is None and hmw is None and lmw is None:
        return "SEC: —"

    parts = []
    if mon is not None:
        parts.append(f"{_fmt_pct(mon)} monomer")
    if hmw is not None:
        parts.append(f"{_fmt_pct(hmw)} HMW")
    if lmw is not None:
        parts.append(f"{_fmt_pct(lmw)} LMW")
    return " / ".join(parts) if parts else "SEC: —"


def _summarize_endotoxin(r: Any) -> str:
    prt = getattr(r, "primary_result_text", None)
    if prt:
        return str(prt)

    out = _loads(getattr(r, "derived_outputs_json", None)) or _loads(getattr(r, "results_json", None))
    val = out.get("value_eu_ml")
    lim = out.get("limit_eu_ml")

    if val is None and lim is None:
        return "Endotoxin: —"
    if val is not None and lim is not None:
        return f"{val} EU/mL (limit {lim})"
    if val is not None:
        return f"{val} EU/mL"
    return f"limit {lim} EU/mL"


def _summarize_binding(r: Any) -> str:
    prt = getattr(r, "primary_result_text", None)
    if prt:
        return str(prt)

    out = _loads(getattr(r, "derived_outputs_json", None)) or _loads(getattr(r, "results_json", None))
    kd = out.get("kd_nM")
    if kd is None:
        return f"{getattr(r, 'method', 'Binding')}: KD —"
    return f"KD {kd} nM"


ASSAYS: list[AssayDef] = [
    AssayDef(key="SEC", display_name="SEC", match=_is_sec, summarize=_summarize_sec),
    AssayDef(key="Binding", display_name="Binding", match=_is_binding, summarize=_summarize_binding),
    AssayDef(key="Endotoxin", display_name="Endotoxin", match=_is_endotoxin, summarize=_summarize_endotoxin),
]


def assay_key(record: Any) -> str:
    for a in ASSAYS:
        try:
            if a.match(record):
                return a.key
        except Exception:
            continue
    dt = getattr(record, "data_type", None) or "Unknown"
    m = getattr(record, "method", None) or "Unknown"
    return f"{dt}/{m}"


def assay_display_name(key: str) -> str:
    for a in ASSAYS:
        if a.key == key:
            return a.display_name
    return key


def record_result_text(record: Any) -> str:
    prt = getattr(record, "primary_result_text", None)
    if prt:
        return str(prt)

    key = assay_key(record)
    for a in ASSAYS:
        if a.key == key:
            try:
                return a.summarize(record)
            except Exception:
                break

    # Generic fallback: show a few keys from derived_outputs_json or results_json.
    out = _loads(getattr(record, "derived_outputs_json", None))
    if out:
        items = []
        for k in sorted(out.keys()):
            v = out.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            items.append(f"{k}={v}")
            if len(items) >= 6:
                break
        if items:
            return "; ".join(items)

    out2 = _loads(getattr(record, "results_json", None))
    if out2:
        items = []
        for k in sorted(out2.keys()):
            v = out2.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            items.append(f"{k}={v}")
            if len(items) >= 6:
                break
        if items:
            return "; ".join(items)

    return "—"
