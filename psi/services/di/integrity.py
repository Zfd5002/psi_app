from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Dict, Iterable, List, Tuple


# Machine-local / debug-only keys that must never contribute to integrity hashes.
MACHINE_LOCAL_INPUT_KEYS = {"policy_path"}


def _stable_json(obj: Any) -> str:
    """Deterministic JSON serialization.

    Keep settings aligned with DI snapshot serialization.
    """

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def canonical_inputs_for_integrity(inputs_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Return the canonical inputs payload used for integrity hashing.

    This explicitly strips machine-local/debug-only keys (e.g., policy_path).
    """

    out: Dict[str, Any] = {}
    for k, v in (inputs_obj or {}).items():
        if k in MACHINE_LOCAL_INPUT_KEYS:
            continue
        out[k] = v
    return out


def evidence_fingerprint_payload(
    *,
    metric_tuples: Iterable[Tuple[str, str, str, str, str]],
) -> List[List[str]]:
    """Return a JSON-friendly payload for evidence fingerprint hashing."""

    return [[a, b, c, d, e] for (a, b, c, d, e) in metric_tuples]


def compute_evidence_fingerprint(*, used_by_metric: Dict[str, Any]) -> str:
    """Compute a deterministic fingerprint over *selected evidence only*.

    For each metric_key (sorted), include:
      - metric_key
      - measurement_id
      - qc_status
      - unit
      - comparator

    All None values are normalized to "" for stability.
    """

    tuples: List[Tuple[str, str, str, str, str]] = []
    for mk in sorted(list((used_by_metric or {}).keys())):
        ev = used_by_metric[mk]
        measurement_id = str(getattr(ev, "measurement_id", "") or "")
        qc_status = str(getattr(ev, "qc_status", "") or "")
        unit = str(getattr(ev, "unit", "") or "")
        comparator = str(getattr(ev, "comparator", "") or "")
        tuples.append((str(mk), measurement_id, qc_status, unit, comparator))

    payload = evidence_fingerprint_payload(metric_tuples=tuples)
    return _sha256_hex(_stable_json(payload))


def compute_snapshot_content_hash(
    *,
    inputs_obj: Dict[str, Any],
    outputs_obj: Dict[str, Any],
    evidence_ids: List[int],
) -> str:
    """Compute a deterministic snapshot content hash.

    AUTHORITATIVE SNAPSHOT PAYLOAD:
      {
        "inputs": inputs_obj stripped of machine-local debug fields,
        "outputs": outputs_obj with provenance.integrity removed (to avoid self-reference),
        "evidence_ids": evidence_ids
      }

    The integrity block is excluded so the hash does not depend on itself.
    """

    canon_inputs = canonical_inputs_for_integrity(inputs_obj or {})

    out_copy = copy.deepcopy(outputs_obj or {})
    prov = out_copy.get("provenance")
    if isinstance(prov, dict) and "integrity" in prov:
        prov = dict(prov)
        prov.pop("integrity", None)
        out_copy["provenance"] = prov

    payload = {
        "inputs": canon_inputs,
        "outputs": out_copy,
        "evidence_ids": list(evidence_ids or []),
    }

    return _sha256_hex(_stable_json(payload))
