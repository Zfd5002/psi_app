"""DI enrichment orchestrator (refactor-only).

This module intentionally delegates to focused helpers:
- SoE builders
- metric evaluation
- risk flag enrichment
- coverage fingerprinting + suggestions
"""

from psi.services.di.coverage import coverage_fingerprint_payload, derive_suggestions
from psi.services.di.metric_eval import derive_metric_evaluations
from psi.services.di.risk_flags import derive_risk_flags_enriched
from psi.services.di.soe import build_soe_v0_2, build_soe_v0_3
