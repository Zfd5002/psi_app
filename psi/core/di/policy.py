from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


def _canonical_json_bytes(obj: Any) -> bytes:
    # Stable: sorted keys, no whitespace drift, UTF-8.
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")


def canonical_policy_json(policy: Dict[str, Any]) -> str:
    """Return the canonical JSON string used for hashing + snapshot embedding.

    NOTE: In v1.2.9d, this canonical form is used for *policy_body* (evaluation semantics),
    not the full policy package.
    """
    return _canonical_json_bytes(policy).decode("utf-8")


def sha256_hex_of_canonical_json(obj: Any) -> str:
    h = hashlib.sha256()
    h.update(_canonical_json_bytes(obj))
    return h.hexdigest()


def policy_hash(policy: Dict[str, Any]) -> str:
    """Backward-compatible alias for the policy semantics hash (policy_body only)."""
    return sha256_hex_of_canonical_json(policy)


def canonical_package_json(pkg: Dict[str, Any]) -> str:
    return _canonical_json_bytes(pkg).decode("utf-8")


@dataclass(frozen=True)
class LoadedPolicy:
    # Full structured policy package JSON.
    package: Dict[str, Any]
    # Policy evaluation semantics (canonical policy_body only).
    policy_body: Dict[str, Any]
    # REQUIRED dual-hash strategy.
    policy_semantics_hash: str
    policy_package_hash: str
    # Canonical JSON strings (deterministic, stable).
    policy_body_canonical_json: str
    policy_package_canonical_json: str
    source_name: str

    @property
    def name(self) -> str:
        return str(self.package.get("policy_name") or "")

    @property
    def version(self) -> str:
        return str(self.package.get("policy_version") or "")

    @property
    def policy_id(self) -> str:
        return str(self.package.get("policy_id") or "")

    @property
    def schema_version(self) -> str:
        return str(self.package.get("schema_version") or "")

    @property
    def decision_key(self) -> str:
        scope = self.package.get("decision_scope")
        if isinstance(scope, dict) and scope.get("decision_key"):
            return str(scope.get("decision_key") or "")
        # Back-compat: older policies stored decision_key in the policy body.
        return str(self.policy_body.get("decision_key") or "")

    @property
    def template_key(self) -> str:
        return str(self.package.get("template_key") or "")

    @property
    def decision_scope(self) -> Any:
        return self.package.get("decision_scope")

    @property
    def experiment_catalog_ref(self) -> Dict[str, str]:
        ref = self.package.get("experiment_catalog_ref")
        if isinstance(ref, dict):
            return {"catalog_id": str(ref.get("catalog_id") or ""), "catalog_version": str(ref.get("catalog_version") or "")}
        return {"catalog_id": "", "catalog_version": ""}

    @property
    def changelog(self) -> Any:
        return self.package.get("changelog")

    # Back-compat fields used by older code paths / rules_version.
    @property
    def hash(self) -> str:
        return self.policy_semantics_hash

    @property
    def canonical_json(self) -> str:
        return self.policy_body_canonical_json


def load_policy(path: Path) -> LoadedPolicy:
    raw = json.loads(path.read_text(encoding="utf-8"))

    # v1.2.9d: policies are packaged. Legacy policies are wrapped.
    if isinstance(raw, dict) and isinstance(raw.get("policy_body"), dict):
        pkg = raw
        body = raw.get("policy_body") or {}
    else:
        pkg = _wrap_legacy_policy_as_package(raw if isinstance(raw, dict) else {})
        body = pkg.get("policy_body") or {}

    semantics_hash = sha256_hex_of_canonical_json(body)
    package_hash = sha256_hex_of_canonical_json(pkg)

    return LoadedPolicy(
        package=pkg,
        policy_body=body,
        policy_semantics_hash=semantics_hash,
        policy_package_hash=package_hash,
        policy_body_canonical_json=canonical_policy_json(body),
        policy_package_canonical_json=canonical_package_json(pkg),
        source_name=path.name,
    )


def _wrap_legacy_policy_as_package(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a legacy v1.2.9c policy into the v1.2.9d policy package schema.

    This is a compatibility bridge so older policy files can still run.
    New policies should be authored as packages.
    """
    return {
        "policy_id": str(raw.get("policy_name") or "legacy_policy"),
        "policy_version": str(raw.get("version") or ""),
        "policy_name": str(raw.get("policy_name") or ""),
        "schema_version": "di.policy_package.v0_1",
        "template_key": str(raw.get("decision_key") or ""),
        "decision_scope": {"decision_key": str(raw.get("decision_key") or ""), "scope_type": str(raw.get("scope_type") or "")},
        "changelog": [],
        "experiment_catalog_ref": {},
        "policy_body": raw,
    }
