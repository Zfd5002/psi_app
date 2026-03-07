from __future__ import annotations

from typing import Iterable

from psi.services.builder_ops import PointMutation


def validate_primary_id(primary_id: str) -> list[str]:
    value = str(primary_id or "").strip()
    if not value:
        return ["New primary ID is required."]
    return []


def validate_parent_exists(parent_exists: bool) -> list[str]:
    if parent_exists:
        return []
    return ["Parent molecule not found."]


def is_valid(errors: Iterable[str]) -> bool:
    return not any(str(e or "").strip() for e in errors)


def validate_target_component_exists(*, component_name: str, available_components: Iterable[str]) -> list[str]:
    name = str(component_name or "").strip()
    available = {str(c or "").strip() for c in available_components}
    if not name:
        return ["Target component is required."]
    if name not in available:
        return [f"Target component not found: {name}"]
    return []


def validate_point_mutations_not_empty(mutations: list[PointMutation]) -> list[str]:
    if mutations:
        return []
    return ["At least one valid point mutation is required."]


def validate_heavy_chain_for_fc_swap(*, available_components: Iterable[str]) -> list[str]:
    available = {str(c or "").strip() for c in available_components}
    if "HC1" in available:
        return []
    return ["Heavy chain HC1 is required for Fc swap."]


def validate_heavy_chain_for_kih(*, available_components: Iterable[str]) -> list[str]:
    available = {str(c or "").strip() for c in available_components}
    if "HC1" in available:
        return []
    return ["Heavy chain HC1 is required for KIH operation."]
