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


@dataclass(frozen=True)
class LoadedProgressPolicy:
    policy: Dict[str, Any]
    policy_hash: str
    canonical_json: str
    source_name: str

    @property
    def policy_id(self) -> str:
        return str(self.policy.get("policy_id") or "")

    @property
    def policy_version(self) -> str:
        return str(self.policy.get("policy_version") or "")


@dataclass(frozen=True)
class LoadedTemplatePrerequisites:
    policy: Dict[str, Any]
    policy_hash: str
    canonical_json: str
    source_name: str


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


def _validate_progress_policy(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Progress policy JSON must be an object")
    early = raw.get("early_milestones")
    di_m = raw.get("di_milestones")
    if not isinstance(early, dict):
        raise ValueError("progress policy early_milestones must be an object")
    if not isinstance(di_m, dict):
        raise ValueError("progress policy di_milestones must be an object")

    norm_early: Dict[str, list[str]] = {}
    for k in sorted([str(x) for x in early.keys()]):
        vals = early.get(k)
        if not isinstance(vals, list):
            raise ValueError(f"progress policy early_milestones[{k}] must be a list")
        out = [str(x).strip() for x in vals if str(x).strip()]
        if len(out) != len(set(out)):
            raise ValueError(f"progress policy early_milestones[{k}] contains duplicates")
        norm_early[k] = out

    norm_di: Dict[str, str] = {}
    for k in sorted([str(x) for x in di_m.keys()]):
        v = str(di_m.get(k) or "").strip()
        if not v:
            raise ValueError(f"progress policy di_milestones[{k}] must be a non-empty string")
        norm_di[k] = v

    out = dict(raw)
    out["early_milestones"] = norm_early
    out["di_milestones"] = norm_di
    return out


def load_progress_policy(path: Path) -> LoadedProgressPolicy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = _validate_progress_policy(raw)
    canon = canonical_package_json(validated)
    h = sha256_hex_of_canonical_json(validated)
    return LoadedProgressPolicy(policy=validated, policy_hash=h, canonical_json=canon, source_name=path.name)


def load_progress_policy_v0_1() -> LoadedProgressPolicy:
    pol_path = Path(__file__).resolve().parent / "catalogs" / "progress_policy_v0_1.json"
    return load_progress_policy(pol_path)


def _validate_template_prerequisites(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("template prerequisites JSON must be an object")
    mappings = raw.get("template_prerequisites")
    if not isinstance(mappings, dict):
        raise ValueError("template_prerequisites must be an object")
    norm: Dict[str, list[str]] = {}
    for k in sorted([str(x) for x in mappings.keys() if str(x).strip()]):
        vals = mappings.get(k)
        if not isinstance(vals, list):
            raise ValueError(f"template_prerequisites[{k}] must be a list")
        items = [str(x).strip() for x in vals if str(x).strip()]
        if len(items) != len(set(items)):
            raise ValueError(f"template_prerequisites[{k}] contains duplicates")
        norm[k] = items
    out = dict(raw)
    out["template_prerequisites"] = norm
    return out


def load_template_prerequisites(path: Path) -> LoadedTemplatePrerequisites:
    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = _validate_template_prerequisites(raw)
    canon = canonical_package_json(validated)
    h = sha256_hex_of_canonical_json(validated)
    return LoadedTemplatePrerequisites(policy=validated, policy_hash=h, canonical_json=canon, source_name=path.name)


def load_template_prerequisites_v0_1() -> LoadedTemplatePrerequisites:
    pol_path = Path(__file__).resolve().parent / "catalogs" / "template_prerequisites_v0_1.json"
    return load_template_prerequisites(pol_path)
