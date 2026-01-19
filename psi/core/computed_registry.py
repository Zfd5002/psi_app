from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


ComputeFn = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Calculator:
    key: str
    label: str
    tier: str  # FAST | HEAVY
    fn: ComputeFn


_CALCULATORS: Dict[str, Calculator] = {}


def register_calculator(*, key: str, label: str, tier: str, fn: ComputeFn) -> None:
    """Register a computed-property calculator.

    Core registers FAST calculators at import time.
    Extensions may register HEAVY calculators.
    """
    _CALCULATORS[key] = Calculator(key=key, label=label, tier=tier, fn=fn)


def list_calculators(*, tier: Optional[str] = None) -> List[Calculator]:
    out = list(_CALCULATORS.values())
    if tier:
        out = [c for c in out if c.tier == tier]
    return sorted(out, key=lambda c: (c.tier, c.key))


def get_calculator(key: str) -> Optional[Calculator]:
    return _CALCULATORS.get(key)
