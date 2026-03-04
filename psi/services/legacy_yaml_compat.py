from __future__ import annotations

from typing import Any

from psi.core.decision_engine import load_rules as _load_rules
from psi.core.decision_engine import run_decision as _run_decision


def load_rules_legacy_yaml(path: str) -> dict[str, Any]:
    """Compatibility wrapper for legacy YAML rule loading.

    Governance note:
    - This path exists for historical parity routes only.
    - It does not alter DI snapshot semantics used by policy-as-data DI.
    """

    out = _load_rules(path)
    return out if isinstance(out, dict) else {}


def run_decision_legacy_yaml(rules: dict[str, Any], decision_key: str, evidence_rows: list[Any]) -> dict[str, Any]:
    """Compatibility wrapper for legacy YAML decision execution."""

    out = _run_decision(rules=rules, decision_key=decision_key, evidence_rows=evidence_rows)
    return out if isinstance(out, dict) else {}
