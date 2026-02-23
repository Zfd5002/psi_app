from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from psi.core.di.policy import canonical_package_json, sha256_hex_of_canonical_json


@dataclass(frozen=True)
class LoadedCatalog:
    catalog: Dict[str, Any]
    catalog_hash: str
    canonical_json: str
    source_name: str

    @property
    def catalog_id(self) -> str:
        return str(self.catalog.get("catalog_id") or "")

    @property
    def catalog_version(self) -> str:
        return str(self.catalog.get("catalog_version") or "")

    @property
    def schema_version(self) -> str:
        return str(self.catalog.get("schema_version") or "")


def load_catalog(path: Path) -> LoadedCatalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Catalog JSON must be an object")
    canon = canonical_package_json(raw)
    h = sha256_hex_of_canonical_json(raw)
    return LoadedCatalog(catalog=raw, catalog_hash=h, canonical_json=canon, source_name=path.name)


def load_experiment_catalog_v0_1() -> LoadedCatalog:
    """Load the canonical experiment catalog from the core catalogs directory."""
    cat_path = Path(__file__).resolve().parent / "catalogs" / "experiment_catalog_v0_1.json"
    return load_catalog(cat_path)
