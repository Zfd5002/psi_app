from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

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


@dataclass(frozen=True)
class LoadedConfidencePolicy:
    policy: Dict[str, Any]
    policy_hash: str
    canonical_json: str
    source_name: str


@dataclass(frozen=True)
class LoadedReplayPolicyCompat:
    catalog: Dict[str, Any]
    catalog_hash: str
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


def _validate_experiment_catalog(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("experiment catalog JSON must be an object")
    exps = raw.get("experiments")
    if not isinstance(exps, list):
        raise ValueError("experiment catalog experiments must be a list")
    seen_keys: set[str] = set()
    out_exps: List[Dict[str, Any]] = []
    for i, e in enumerate(exps):
        if not isinstance(e, dict):
            raise ValueError(f"experiment catalog experiments[{i}] must be an object")
        ek = str(e.get("experiment_key") or "").strip()
        if not ek:
            raise ValueError(f"experiment catalog experiments[{i}].experiment_key must be non-empty")
        if ek in seen_keys:
            raise ValueError(f"experiment catalog duplicate experiment_key: {ek}")
        seen_keys.add(ek)
        out_e = dict(e)
        rr = e.get("resolves_risk_flags")
        if rr is None:
            out_e["resolves_risk_flags"] = []
        else:
            if not isinstance(rr, list):
                raise ValueError(f"experiment catalog experiments[{i}].resolves_risk_flags must be a list")
            rr_items = [str(x).strip() for x in rr if str(x).strip()]
            if len(rr_items) != len(set(rr_items)):
                raise ValueError(f"experiment catalog experiments[{i}].resolves_risk_flags contains duplicates")
            out_e["resolves_risk_flags"] = sorted(rr_items)
        out_exps.append(out_e)
    out = dict(raw)
    out["experiments"] = out_exps
    return out


def load_experiment_catalog(path: Path) -> LoadedCatalog:
    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = _validate_experiment_catalog(raw)
    canon = canonical_package_json(validated)
    h = sha256_hex_of_canonical_json(validated)
    return LoadedCatalog(catalog=validated, catalog_hash=h, canonical_json=canon, source_name=path.name)


def load_experiment_catalog_v0_2() -> LoadedCatalog:
    cat_path = Path(__file__).resolve().parent / "catalogs" / "experiment_catalog_v0_2.json"
    return load_experiment_catalog(cat_path)


def load_experiment_catalog_latest() -> LoadedCatalog:
    cat_dir = Path(__file__).resolve().parent / "catalogs"
    patt = re.compile(r"^experiment_catalog_v(\d+)_(\d+)\.json$")
    candidates: list[tuple[int, int, Path]] = []
    for p in sorted(cat_dir.glob("experiment_catalog_v*_*.json")):
        m = patt.match(p.name)
        if not m:
            continue
        candidates.append((int(m.group(1)), int(m.group(2)), p))
    if not candidates:
        raise FileNotFoundError("No experiment_catalog_v*_*.json files found")
    _, _, latest_path = sorted(candidates, key=lambda t: (t[0], t[1], t[2].name))[-1]
    return load_experiment_catalog(latest_path)


def build_experiment_risk_flag_index(*, catalog: Dict[str, Any]) -> Dict[str, List[str]]:
    exps = catalog.get("experiments") if isinstance(catalog, dict) else None
    if not isinstance(exps, list):
        return {}
    tmp: Dict[str, set[str]] = {}
    for e in exps:
        if not isinstance(e, dict):
            continue
        ek = str(e.get("experiment_key") or "").strip()
        if not ek:
            continue
        rr = e.get("resolves_risk_flags") if isinstance(e.get("resolves_risk_flags"), list) else []
        for rf in sorted({str(x).strip() for x in rr if str(x).strip()}):
            tmp.setdefault(rf, set()).add(ek)
    return {rf: sorted(list(tmp.get(rf) or set())) for rf in sorted(tmp.keys())}


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


def load_progress_policy_v0_2() -> LoadedProgressPolicy:
    pol_path = Path(__file__).resolve().parent / "catalogs" / "progress_policy_v0_2.json"
    return load_progress_policy(pol_path)


def load_progress_policy_latest() -> LoadedProgressPolicy:
    """Deterministic latest resolver (explicit mapping, no filesystem scan)."""
    return load_progress_policy_v0_2()


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


def load_template_prerequisites_latest() -> LoadedTemplatePrerequisites:
    cat_dir = Path(__file__).resolve().parent / "catalogs"
    patt = re.compile(r"^template_prerequisites_v(\d+)_(\d+)\.json$")
    candidates: list[tuple[int, int, Path]] = []
    for p in sorted(cat_dir.glob("template_prerequisites_v*_*.json")):
        m = patt.match(p.name)
        if not m:
            continue
        candidates.append((int(m.group(1)), int(m.group(2)), p))
    if not candidates:
        raise FileNotFoundError("No template_prerequisites_v*_*.json files found")
    _, _, latest_path = sorted(candidates, key=lambda t: (t[0], t[1], t[2].name))[-1]
    return load_template_prerequisites(latest_path)


def _validate_confidence_policy(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("confidence policy JSON must be an object")
    comp_order = raw.get("component_order")
    component_rules = raw.get("component_rules")
    scalar_rules = raw.get("scalar_rules")
    if not isinstance(comp_order, list) or not comp_order:
        raise ValueError("confidence policy component_order must be a non-empty list")
    if not isinstance(scalar_rules, dict):
        raise ValueError("confidence policy scalar_rules must be an object")
    comps = [str(x).strip() for x in comp_order if str(x).strip()]
    if len(comps) != len(set(comps)):
        raise ValueError("confidence policy component_order contains duplicates")
    norm_component_rules: Dict[str, Any] = {}
    if component_rules is not None:
        if not isinstance(component_rules, dict):
            raise ValueError("confidence policy component_rules must be an object when present")
        for ck in comps:
            rv = component_rules.get(ck)
            if not isinstance(rv, dict):
                raise ValueError(f"confidence policy component_rules.{ck} must be an object")
            label = str(rv.get("label") or "").strip()
            if not label:
                raise ValueError(f"confidence policy component_rules.{ck}.label must be non-empty")
            norm_rv = dict(rv)
            norm_rv["label"] = label
            norm_component_rules[ck] = norm_rv
    out_rules = dict(scalar_rules)
    if int(out_rules.get("medium_concerns_amber_min") or 0) <= 0:
        raise ValueError("confidence policy scalar_rules.medium_concerns_amber_min must be > 0")
    hc = str(out_rules.get("high_concern_escalates_to") or "").strip().lower()
    if hc not in {"amber", "green", "unknown"}:
        raise ValueError("confidence policy scalar_rules.high_concern_escalates_to must be amber|green|unknown")
    out_rules["high_concern_escalates_to"] = hc
    out_rules["medium_concerns_amber_min"] = int(out_rules.get("medium_concerns_amber_min"))
    out_rules["unknown_when_assessed_count_is_zero"] = bool(out_rules.get("unknown_when_assessed_count_is_zero"))
    out = dict(raw)
    out["component_order"] = comps
    if component_rules is not None:
        out["component_rules"] = norm_component_rules
    mta = raw.get("multi_template_aggregation")
    if mta is not None:
        if not isinstance(mta, dict):
            raise ValueError("confidence policy multi_template_aggregation must be an object when present")
        strategy = str(mta.get("strategy") or "").strip()
        if not strategy:
            raise ValueError("confidence policy multi_template_aggregation.strategy must be non-empty")
        cmo = mta.get("component_merge_order")
        if cmo is not None:
            if not isinstance(cmo, list):
                raise ValueError("confidence policy multi_template_aggregation.component_merge_order must be a list when present")
            cmo_items = [str(x).strip() for x in cmo if str(x).strip()]
            if cmo_items != [c for c in cmo_items]:
                raise ValueError("confidence policy multi_template_aggregation.component_merge_order normalization failed")
            if len(cmo_items) != len(set(cmo_items)):
                raise ValueError("confidence policy multi_template_aggregation.component_merge_order contains duplicates")
            if any(x not in comps for x in cmo_items):
                raise ValueError("confidence policy multi_template_aggregation.component_merge_order contains unknown component keys")
        out_mta = dict(mta)
        out_mta["strategy"] = strategy
        if cmo is not None:
            out_mta["component_merge_order"] = cmo_items
        if "weighted_scoring" in out_mta:
            out_mta["weighted_scoring"] = bool(out_mta.get("weighted_scoring"))
        out["multi_template_aggregation"] = out_mta
    out["scalar_rules"] = out_rules
    return out


def load_confidence_policy(path: Path) -> LoadedConfidencePolicy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = _validate_confidence_policy(raw)
    canon = canonical_package_json(validated)
    h = sha256_hex_of_canonical_json(validated)
    return LoadedConfidencePolicy(policy=validated, policy_hash=h, canonical_json=canon, source_name=path.name)


def load_confidence_policy_v0_1() -> LoadedConfidencePolicy:
    pol_path = Path(__file__).resolve().parent / "catalogs" / "confidence_policy_v0_1.json"
    return load_confidence_policy(pol_path)


def load_confidence_policy_v0_2() -> LoadedConfidencePolicy:
    pol_path = Path(__file__).resolve().parent / "catalogs" / "confidence_policy_v0_2.json"
    return load_confidence_policy(pol_path)


def load_confidence_policy_v0_3() -> LoadedConfidencePolicy:
    pol_path = Path(__file__).resolve().parent / "catalogs" / "confidence_policy_v0_3.json"
    return load_confidence_policy(pol_path)


def load_confidence_policy_latest() -> LoadedConfidencePolicy:
    """Deterministic latest resolver (explicit mapping, no filesystem scan)."""
    return load_confidence_policy_v0_3()


def _validate_replay_policy_compat(raw: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("replay policy compat catalog must be an object")
    items = raw.get("policies")
    if not isinstance(items, list):
        raise ValueError("replay policy compat catalog policies must be a list")
    norm: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"replay policy compat policies[{i}] must be an object")
        pid = str(item.get("policy_id") or "").strip()
        pver = str(item.get("policy_version") or "").strip()
        if not pid or not pver:
            raise ValueError(f"replay policy compat policies[{i}] policy_id/policy_version must be non-empty")
        key = (pid, pver)
        if key in seen:
            raise ValueError(f"replay policy compat duplicate entry for {pid}@{pver}")
        seen.add(key)
        out = dict(item)
        out["policy_id"] = pid
        out["policy_version"] = pver
        out["allow_exact_hash_fallback"] = bool(item.get("allow_exact_hash_fallback"))
        if item.get("fallback_policy_id") is not None:
            out["fallback_policy_id"] = str(item.get("fallback_policy_id") or "").strip()
        if item.get("fallback_policy_version") is not None:
            out["fallback_policy_version"] = str(item.get("fallback_policy_version") or "").strip()
        norm.append(out)
    out = dict(raw)
    out["policies"] = sorted(norm, key=lambda x: (str(x.get("policy_id") or ""), str(x.get("policy_version") or "")))
    return out


def load_replay_policy_compat(path: Path) -> LoadedReplayPolicyCompat:
    raw = json.loads(path.read_text(encoding="utf-8"))
    validated = _validate_replay_policy_compat(raw)
    canon = canonical_package_json(validated)
    h = sha256_hex_of_canonical_json(validated)
    return LoadedReplayPolicyCompat(catalog=validated, catalog_hash=h, canonical_json=canon, source_name=path.name)


def load_replay_policy_compat_v0_1() -> LoadedReplayPolicyCompat:
    p = Path(__file__).resolve().parent / "catalogs" / "replay_policy_compat_v0_1.json"
    return load_replay_policy_compat(p)


def load_replay_policy_compat_latest() -> LoadedReplayPolicyCompat:
    """Deterministic latest resolver (explicit mapping, no filesystem scan)."""
    return load_replay_policy_compat_v0_1()
