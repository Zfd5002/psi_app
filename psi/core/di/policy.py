from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


def _canonical_json_bytes(obj: Any) -> bytes:
    # Stable: sorted keys, no whitespace drift, UTF-8.
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return s.encode("utf-8")


def canonical_policy_json(policy: Dict[str, Any]) -> str:
    """Return the canonical JSON string used for hashing + snapshot embedding."""
    return _canonical_json_bytes(policy).decode("utf-8")


def policy_hash(policy: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(_canonical_json_bytes(policy))
    return h.hexdigest()


@dataclass(frozen=True)
class LoadedPolicy:
    policy: Dict[str, Any]
    hash: str
    canonical_json: str
    source_name: str

    @property
    def name(self) -> str:
        return str(self.policy.get("policy_name") or "")

    @property
    def version(self) -> str:
        return str(self.policy.get("version") or "")

    @property
    def decision_key(self) -> str:
        return str(self.policy.get("decision_key") or "")


def load_policy(path: Path) -> LoadedPolicy:
    raw = json.loads(path.read_text(encoding="utf-8"))
    ph = policy_hash(raw)
    return LoadedPolicy(policy=raw, hash=ph, canonical_json=canonical_policy_json(raw), source_name=path.name)
