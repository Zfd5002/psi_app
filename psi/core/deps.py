"""Centralized dependency / capability gates.

PSI has a *core* install mode (ELN + viewer) and an optional *heavy compute*
mode (domains, numbering, etc.).

Heavy compute producers should import optional dependencies lazily and gate
execution through these helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from importlib import metadata


def anarci_available() -> bool:
    try:
        import anarci  # noqa: F401

        return True
    except Exception:
        return False


def abnumber_available() -> bool:
    try:
        import abnumber  # noqa: F401

        return True
    except Exception:
        return False


def biopython_available() -> bool:
    try:
        import Bio  # noqa: F401

        return True
    except Exception:
        return False


@dataclass(frozen=True)
class DependencyProbe:
    available: bool
    version: str | None
    error: str | None


def _probe_dependency(import_name: str, *, dist_name: str | None = None) -> DependencyProbe:
    try:
        importlib.import_module(import_name)
    except Exception as e:
        return DependencyProbe(available=False, version=None, error=f"{type(e).__name__}: {e}")

    ver = None
    try:
        ver = metadata.version(dist_name or import_name)
    except Exception:
        ver = None
    return DependencyProbe(available=True, version=ver, error=None)


def numbering_dependency_status() -> dict:
    """Detailed probe for antibody-numbering runtime dependencies."""
    ab = _probe_dependency("abnumber", dist_name="abnumber")
    an = _probe_dependency("anarci", dist_name="anarci")
    bp = _probe_dependency("Bio", dist_name="biopython")
    components = {
        "abnumber": {"available": ab.available, "version": ab.version, "error": ab.error},
        "anarci": {"available": an.available, "version": an.version, "error": an.error},
        "biopython": {"available": bp.available, "version": bp.version, "error": bp.error},
    }
    missing = [name for name, meta in components.items() if not bool(meta.get("available"))]
    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "components": components,
    }


@dataclass(frozen=True)
class HeavyComputeGate:
    ok: bool
    code: str
    reason: str


def heavy_compute_available_for_molecule(molecule, *, require: tuple[str, ...] = ("anarci", "abnumber", "biopython")) -> HeavyComputeGate:
    """Return whether heavy compute should run for a molecule.

    Skip reasons are intentionally stable strings so UI can show actionable copy.
    """

    # Format gating
    fmt = (getattr(molecule, "molecule_format", None) or "").strip()
    if fmt not in ("IgG", "scFv"):
        return HeavyComputeGate(False, "format_not_supported", f"Format '{fmt or 'unknown'}' is not supported for heavy compute")

    # Per-molecule toggle
    if int(getattr(molecule, "heavy_compute_enabled", 0) or 0) != 1:
        return HeavyComputeGate(False, "heavy_compute_disabled", "Heavy compute disabled for this molecule")

    # Dependency tier
    missing = []
    req = set(require or ())
    if "anarci" in req and not anarci_available():
        missing.append("ANARCI")
    if "abnumber" in req and not abnumber_available():
        missing.append("abnumber")
    # biopython is used by ANARCI and other pipelines; include for clarity.
    if "biopython" in req and not biopython_available():
        missing.append("biopython")

    if missing:
        return HeavyComputeGate(
            False,
            "dependency_missing",
            "Heavy compute dependencies not installed: " + ", ".join(missing),
        )

    return HeavyComputeGate(True, "ok", "")
