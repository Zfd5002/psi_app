"""Structure-informed predictors (HEAVY compute).

v1.01: This module provides the extension hook and a placeholder calculator.
Actual predictors (secondary structure, accessibility, homology modeling, etc.)
are intentionally non-goals in this version and should be added incrementally.

This extension is gated by:
  1) global env var PSI_ENABLE_HEAVY_COMPUTE=1
  2) per-molecule toggle molecules.heavy_compute_enabled=1
"""

from __future__ import annotations

from typing import Any, Dict

from psi.core.computed_registry import register_calculator


def init_extension(app=None) -> None:
    def placeholder(ctx: dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "not_implemented",
            "message": (
                "Structure-informed predictions are architected as an extension and gated by config + UI toggle. "
                "Implement predictors inside psi/extensions/structure in a future version."
            ),
        }

    register_calculator(key="heavy.structure.placeholder", label="Structure-informed predictions (placeholder)", tier="HEAVY", fn=placeholder)
