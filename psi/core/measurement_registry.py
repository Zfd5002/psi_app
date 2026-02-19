"""Measurement registry (export-first).

PSI v1.2.3g

Goals
- Central, deterministic definitions of measurement keys for export.
- No required DB migrations and no producer rewrites in v1.2.3g.
- Registry drives:
  - canonical keys + aliases
  - export column naming + ordering
  - dtype hints
  - unit expectations + explicit conversions (no guessing)

This module is intentionally small and boring. Expand by adding MeasurementDef entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple


@dataclass(frozen=True)
class MeasurementDef:
    canonical_key: str
    label: str
    dtype: str  # "numeric" | "text"
    category: str
    primary_eligible: bool

    export_name: str

    canonical_unit: Optional[str] = None
    allowed_units: Tuple[str, ...] = ()

    # conversions: (from_unit, to_unit) -> function(value)->value
    conversions: Tuple[Tuple[str, str, Callable[[float], float]], ...] = ()

    aliases: Tuple[str, ...] = ()


def normalize_key(raw_key: str) -> str:
    s = (raw_key or "").strip()
    if not s:
        return ""
    s = s.lower()
    # conservative normalization: keep underscores, collapse whitespace
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    return s


def _conv_factor(f: float) -> Callable[[float], float]:
    return lambda x: x * f


# Minimal initial registry aligned to keys used in psi/core/assays.py summarizers
# and typical derived_outputs_json/results_json keys.
MEASUREMENTS: List[MeasurementDef] = [
    # SEC
    MeasurementDef(
        canonical_key="monomer_pct",
        label="Monomer %",
        dtype="numeric",
        category="SEC",
        primary_eligible=True,
        export_name="sec__monomer_pct",
        canonical_unit="%",
        allowed_units=("%",),
        aliases=("monomer%", "monomer_percent", "monomer_pct", "monomer"),
    ),
    MeasurementDef(
        canonical_key="hmw_pct",
        label="HMW %",
        dtype="numeric",
        category="SEC",
        primary_eligible=True,
        export_name="sec__hmw_pct",
        canonical_unit="%",
        allowed_units=("%",),
        aliases=("hmw%", "hmw_percent", "hmw_pct", "hmw"),
    ),
    MeasurementDef(
        canonical_key="lmw_pct",
        label="LMW %",
        dtype="numeric",
        category="SEC",
        primary_eligible=True,
        export_name="sec__lmw_pct",
        canonical_unit="%",
        allowed_units=("%",),
        aliases=("lmw%", "lmw_percent", "lmw_pct", "lmw"),
    ),

    # Binding
    MeasurementDef(
        canonical_key="kd_nm",
        label="KD (nM)",
        dtype="numeric",
        category="Binding",
        primary_eligible=True,
        export_name="binding__kd_nM",
        canonical_unit="nM",
        allowed_units=("nM", "uM", "µM", "pM"),
        conversions=(
            ("uM", "nM", _conv_factor(1000.0)),
            ("µM", "nM", _conv_factor(1000.0)),
            ("pM", "nM", _conv_factor(0.001)),
        ),
        aliases=("kd", "kd_nm", "kd_nM", "kd_nM"),
    ),

    # Endotoxin
    MeasurementDef(
        canonical_key="value_eu_ml",
        label="Endotoxin (EU/mL)",
        dtype="numeric",
        category="Endotoxin",
        primary_eligible=True,
        export_name="endotoxin__value_eu_ml",
        canonical_unit="EU/mL",
        allowed_units=("EU/mL",),
        aliases=("value_eu_ml", "endotoxin_eu_ml", "eu_ml"),
    ),
    MeasurementDef(
        canonical_key="limit_eu_ml",
        label="Endotoxin limit (EU/mL)",
        dtype="numeric",
        category="Endotoxin",
        primary_eligible=False,
        export_name="endotoxin__limit_eu_ml",
        canonical_unit="EU/mL",
        allowed_units=("EU/mL",),
        aliases=("limit_eu_ml", "endotoxin_limit_eu_ml"),
    ),
]


# Build lookup maps
_BY_CANON: Dict[str, MeasurementDef] = {m.canonical_key: m for m in MEASUREMENTS}
_BY_ALIAS: Dict[str, MeasurementDef] = {}
for m in MEASUREMENTS:
    _BY_ALIAS[normalize_key(m.canonical_key)] = m
    for a in m.aliases:
        ak = normalize_key(a)
        if ak:
            _BY_ALIAS[ak] = m


def resolve_def(raw_key: str) -> Optional[MeasurementDef]:
    nk = normalize_key(raw_key)
    if not nk:
        return None
    return _BY_ALIAS.get(nk)


def ordered_defs() -> Sequence[MeasurementDef]:
    return tuple(MEASUREMENTS)


def conversion_to_canonical(defn: MeasurementDef, unit: Optional[str]) -> Optional[Callable[[float], float]]:
    """Return a conversion function to canonical_unit if explicitly defined, else None."""
    if not unit or not defn.canonical_unit:
        return None
    if unit == defn.canonical_unit:
        return lambda x: x

    for u_from, u_to, fn in defn.conversions:
        if u_from == unit and u_to == defn.canonical_unit:
            return fn
    return None
