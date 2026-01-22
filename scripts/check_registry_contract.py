#!/usr/bin/env python3
"""Sanity-check the /api/registry contract.

This is intentionally *not* a full test framework.
It exists to prevent accidental regressions in the dynamic registry
used by "Data → New" and other UI flows.

Usage:
  python scripts/check_registry_contract.py

Exits non-zero on failure.
"""

from __future__ import annotations

import sys
from pathlib import Path
import importlib.util
from typing import Any, Dict, Iterable, List


def _fail(msg: str) -> None:
    print(f"[registry-contract] FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _require_keys(d: Dict[str, Any], keys: List[str], *, where: str) -> None:
    for k in keys:
        if k not in d:
            _fail(f"missing required key '{k}' in {where}")


def _is_list(x: Any) -> bool:
    return isinstance(x, list)


def main() -> int:
    # Allow running from repo checkout without installing as a package.
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))

    # Import registry *without* importing psi.core.__init__ (which pulls in SQLAlchemy).
    # This script should remain usable even if only a minimal environment is available.
    reg_path = repo_root / "psi" / "core" / "registry.py"
    if not reg_path.exists():
        _fail(f"registry module not found at {reg_path}")
    try:
        spec = importlib.util.spec_from_file_location("psi_core_registry", reg_path)
        if spec is None or spec.loader is None:
            _fail("failed to create import spec for registry")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        REGISTRY = getattr(mod, "REGISTRY")
    except Exception as e:
        _fail(f"could not load REGISTRY from {reg_path}: {e}")

    if not isinstance(REGISTRY, dict):
        _fail("REGISTRY is not a dict")

    _require_keys(
        REGISTRY,
        ["domains_ordered", "data_types_by_domain", "data_type_meta", "data_schemas"],
        where="REGISTRY",
    )

    # domains_ordered: ordered list of dicts with key/label/order
    domains = REGISTRY["domains_ordered"]
    if not _is_list(domains) or not domains:
        _fail("domains_ordered must be a non-empty list")
    for i, d in enumerate(domains):
        if not isinstance(d, dict):
            _fail(f"domains_ordered[{i}] is not a dict")
        for k in ("key", "label", "order"):
            if k not in d:
                _fail(f"domains_ordered[{i}] missing '{k}'")

    # data_schemas: {DATA_TYPE: {METHOD: {params_fields: [...], results_fields: [...]}}}
    schemas = REGISTRY["data_schemas"]
    if not isinstance(schemas, dict):
        _fail("data_schemas must be a dict")
    for dt_key, methods in schemas.items():
        if not isinstance(methods, dict):
            _fail(f"data_schemas[{dt_key!r}] must be a dict of methods")
        for m_key, schema in methods.items():
            if not isinstance(schema, dict):
                _fail(f"data_schemas[{dt_key!r}][{m_key!r}] must be a dict")
            for field_list_key in ("params_fields", "results_fields"):
                if field_list_key not in schema:
                    _fail(f"schema missing '{field_list_key}' for {dt_key}/{m_key}")
                if not isinstance(schema[field_list_key], list):
                    _fail(f"{dt_key}/{m_key} '{field_list_key}' must be a list")

    print("[registry-contract] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
