"""Framework-agnostic domain core.

This package is intended to remain stable across PSI versions.
Web/API/CLI layers should import from here, not from web routers.
"""

from .db import SessionLocal, ensure_schema
from .decision_engine import load_rules, run_decision
from .registry import REGISTRY, get_allowed_data_sources_for_evidence

__all__ = [
    "SessionLocal",
    "ensure_schema",
    "load_rules",
    "run_decision",
    "REGISTRY",
    "get_allowed_data_sources_for_evidence",
]
