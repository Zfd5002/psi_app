"""Export Profiles (Foundation).

Profiles provide deterministic, named export configurations for the wide exporter.

Design goals (v1.2.8):
  - Backward-compatible: if no profile is selected, behavior matches current exports.
  - Deterministic: explicit, stable ordering of columns and measurement fields.
  - Safe defaults: profile defaults apply only when a profile is explicitly selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from psi.core.measurement_registry import resolve_def


@dataclass(frozen=True)
class ExportProfileDefaults:
    # If set, applies only when profile selected and caller did not explicitly set qc_mode.
    qc_mode: Optional[str] = None  # none|model_safe|strict


@dataclass(frozen=True)
class ExportProfile:
    name: str
    description: str
    measurement_keys: Tuple[str, ...]
    core_columns: Optional[Tuple[str, ...]] = None
    defaults: ExportProfileDefaults = ExportProfileDefaults()


# NOTE: measurement_keys must use canonical_key values from psi.core.measurement_registry.
PROFILES: Dict[str, ExportProfile] = {
    "ML_core": ExportProfile(
        name="ML_core",
        description="Model-ready core features across SEC, Binding, and Endotoxin. Defaults to QC=model_safe.",
        measurement_keys=(
            "monomer_pct",
            "hmw_pct",
            "lmw_pct",
            "kd_nm",
            "value_eu_ml",
            "limit_eu_ml",
        ),
        defaults=ExportProfileDefaults(qc_mode="model_safe"),
    ),
    "CMC_only": ExportProfile(
        name="CMC_only",
        description="CMC/developability-focused metrics (SEC + Endotoxin). Defaults to QC=strict.",
        measurement_keys=(
            "monomer_pct",
            "hmw_pct",
            "lmw_pct",
            "value_eu_ml",
            "limit_eu_ml",
        ),
        defaults=ExportProfileDefaults(qc_mode="strict"),
    ),
    "Binding_only": ExportProfile(
        name="Binding_only",
        description="Binding-focused metrics (e.g., KD). Defaults to QC=model_safe.",
        measurement_keys=(
            "kd_nm",
        ),
        defaults=ExportProfileDefaults(qc_mode="model_safe"),
    ),
}


def list_profiles() -> Tuple[str, ...]:
    """Return deterministic list of available profile names."""
    return tuple(sorted(PROFILES.keys()))


def get_profile(name: str | None) -> Optional[ExportProfile]:
    if not name:
        return None
    return PROFILES.get(str(name).strip())


def validate_profiles() -> None:
    """Validate registry for internal consistency.

    Raises AssertionError for invalid profiles.
    """
    for pname, p in PROFILES.items():
        assert pname == p.name, f"Profile key '{pname}' must match ExportProfile.name '{p.name}'"
        # measurement key validity
        seen = set()
        for k in p.measurement_keys:
            assert k not in seen, f"Duplicate measurement key '{k}' in profile {pname}"
            seen.add(k)
            # resolve_def accepts aliases; ensure canonical key exists
            d = resolve_def(k)
            assert d is not None and d.canonical_key == k, f"Unknown canonical measurement key '{k}' in profile {pname}"
        # qc defaults
        if p.defaults.qc_mode is not None:
            assert p.defaults.qc_mode in ("none", "model_safe", "strict"), f"Invalid qc_mode default on {pname}"
