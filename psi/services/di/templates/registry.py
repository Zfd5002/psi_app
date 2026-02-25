from __future__ import annotations

from typing import Any, Callable, Dict, List

from psi.services.di.templates.advance_to_in_vivo import evaluate as eval_advance_to_in_vivo
from psi.services.di.templates.ready_for_scaleup_screen import evaluate as eval_ready_for_scaleup_screen


TemplateEvalFn = Callable[..., Dict[str, Any]]


DECISION_KEY_TO_TEMPLATE_KEY: Dict[str, str] = {
    "advance_to_in_vivo": "advance_to_in_vivo.v0_1",
    "ready_for_scaleup_screen": "ready_for_scaleup_screen.v0_1",
}

TEMPLATE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "advance_to_in_vivo.v0_1": {
        "evaluator_version": "di.template.advance_to_in_vivo.v0_2",
        "evaluate": eval_advance_to_in_vivo,
        "enforce_value_functions": True,
        "dependencies": [],
    },
    "ready_for_scaleup_screen.v0_1": {
        "evaluator_version": "di.template.ready_for_scaleup_screen.v0_1",
        "evaluate": eval_ready_for_scaleup_screen,
        "enforce_value_functions": True,
        "dependencies": ["advance_to_in_vivo.v0_1"],
    }
}


def list_template_keys_sorted() -> List[str]:
    return sorted([str(k) for k in TEMPLATE_REGISTRY.keys()])


def template_dependency_graph() -> Dict[str, Any]:
    nodes = list_template_keys_sorted()
    edges: List[Dict[str, str]] = []
    for key in nodes:
        entry = TEMPLATE_REGISTRY.get(key) if isinstance(TEMPLATE_REGISTRY.get(key), dict) else {}
        deps = entry.get("dependencies") if isinstance(entry, dict) and isinstance(entry.get("dependencies"), list) else []
        for dep in sorted([str(x) for x in deps if str(x).strip()]):
            edges.append({"template_key": key, "depends_on": dep})
    return {"schema_version": "di.template_graph.v1", "nodes": nodes, "edges": edges}


def get_template_entry(template_key: str) -> Dict[str, Any]:
    key = str(template_key or "").strip()
    if not key:
        raise ValueError("Missing template_key in policy package")
    entry = TEMPLATE_REGISTRY.get(key)
    if not entry:
        raise ValueError(f"Unknown template_key: {key}")
    return entry


def resolve_template_entry(*, decision_key: str, template_key: str | None) -> Dict[str, Any]:
    dk = str(decision_key or "").strip()
    tk = str(template_key or "").strip()

    if not dk:
        raise ValueError("Missing decision_key")

    expected = DECISION_KEY_TO_TEMPLATE_KEY.get(dk)

    if tk:
        if expected and tk != expected:
            raise ValueError(f"Template key mismatch for decision_key {dk}: policy={tk} expected={expected}")
        return get_template_entry(tk)

    if not expected:
        raise ValueError(f"Unknown decision_key: {dk}")
    return get_template_entry(expected)
