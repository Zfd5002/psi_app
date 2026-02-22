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


def _sorted_list_of_dicts(items: Any, *, key_fields: List[str]) -> List[Dict[str, Any]]:
    """Deterministically sort a list of dict-like objects.

    This is intentionally small-scope and used only for semantic integrity surfaces
    where list ordering should not cause spurious drift.
    """

    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in items:
        if isinstance(it, dict):
            out.append(it)

    def _k(d: Dict[str, Any]) -> str:
        kobj = {f: d.get(f) for f in key_fields}
        return _stable_json(kobj)

    return sorted(out, key=_k)


def canonical_outputs_for_decision_hash(outputs_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical *semantic* subset of outputs for integrity hashing.

    Guiding principle:
    - If policy hashes and evidence fingerprint are unchanged, verification should
      be stable across additive diagnostic/UX fields.

    This function intentionally excludes large descriptive blocks (SoE summaries,
    enrichment packs, and UI-only metadata) that are not part of the authoritative
    decision outcome.
    """

    out = outputs_obj if isinstance(outputs_obj, dict) else {}

    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
    engine = out.get("engine") if isinstance(out.get("engine"), dict) else {}

    # Strip integrity to avoid self-reference.
    prov_no_integrity = dict(prov)
    if isinstance(prov_no_integrity.get("integrity"), dict):
        prov_no_integrity.pop("integrity", None)

    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}

    # Normalize a few known list-like fields in readiness to avoid spurious drift
    # from ordering differences (while keeping behavior unchanged).
    readiness_norm = dict(readiness)
    for k in ("blocking_gates", "blocking_reasons", "assumptions", "required_next_steps"):
        if isinstance(readiness_norm.get(k), list):
            readiness_norm[k] = sorted([str(x) for x in readiness_norm.get(k) if str(x).strip()])
    if isinstance(readiness_norm.get("blockers"), list):
        readiness_norm["blockers"] = _sorted_list_of_dicts(
            readiness_norm.get("blockers"),
            key_fields=["key", "severity", "explanation"],
        )

    gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}

    measurement_ids_used = out.get("measurement_ids_used")
    if isinstance(measurement_ids_used, list):
        mids: List[int] = []
        for x in measurement_ids_used:
            try:
                mids.append(int(x))
            except Exception:
                continue
        measurement_ids_used_norm: List[int] = sorted(list(set(mids)))
    else:
        measurement_ids_used_norm = []

    return {
        "decision_state": out.get("decision_state"),
        "policy": {
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("policy_version"),
            "policy_semantics_hash": policy.get("policy_semantics_hash"),
            "policy_package_hash": policy.get("policy_package_hash"),
        },
        "engine": {
            "engine_id": engine.get("engine_id"),
            "schema_version": engine.get("schema_version"),
            "selector_version": engine.get("selector_version"),
            "evaluator_version": engine.get("evaluator_version"),
            "evaluation_version": engine.get("evaluation_version"),
            "code_version": engine.get("code_version"),
        },
        "provenance": {
            "qc_mode": prov_no_integrity.get("qc_mode"),
            "selection_semantics_version": prov_no_integrity.get("selection_semantics_version"),
            "experiment_catalog": prov_no_integrity.get("experiment_catalog"),
            "inputs_fingerprint": prov_no_integrity.get("inputs_fingerprint"),
        },
        "measurement_ids_used": measurement_ids_used_norm,
        "gate_outcomes": gate_outcomes,
        "readiness": readiness_norm,
    }


def _canon_gate_outcomes_v2(gate_outcomes: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Canonicalize gate outcomes for semantic integrity hashing.

    v2 intentionally hashes only the stable, authoritative outcome signal per gate.
    This avoids spurious drift from additive diagnostic fields (e.g., missing_metrics
    lists, QC notes, explanations) while remaining sensitive to pass/fail changes.
    """

    out: List[Dict[str, Any]] = []
    if not isinstance(gate_outcomes, dict):
        return out
    for gate_key in sorted(gate_outcomes.keys()):
        v = gate_outcomes.get(gate_key)
        status = v.get("status") if isinstance(v, dict) else None
        out.append({"gate": str(gate_key), "status": status})
    return out


def canonical_outputs_for_decision_hash_v2(outputs_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Return a canonical *semantic* subset of outputs for integrity hashing (v2).

    v2 tightens the semantic surface so that:
    - If policy hashes and evidence fingerprint are unchanged, verification returns VERIFIED.

    Compared to v1, v2:
    - Excludes provenance fields (including inputs_fingerprint) from the semantic hash.
    - Canonicalizes gate outcomes to only (gate_key, status) pairs.
    - Excludes freeform explanatory strings from blockers.
    """

    out = outputs_obj if isinstance(outputs_obj, dict) else {}

    policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
    engine = out.get("engine") if isinstance(out.get("engine"), dict) else {}

    readiness = out.get("readiness") if isinstance(out.get("readiness"), dict) else {}
    readiness_norm = dict(readiness)

    # Diagnostic/UX annotations (like freeform QC notes) should not affect the v2
    # decision surface hash. They are derived from warnings and may differ between
    # stored snapshots and anchored replays even when the decision outcome is
    # identical.
    qc_conf = readiness_norm.get("qc_confidence")
    if isinstance(qc_conf, dict):
        qc_conf_norm = dict(qc_conf)
        qc_conf_norm.pop("notes", None)
        readiness_norm["qc_confidence"] = qc_conf_norm

    for k in ("blocking_gates", "blocking_reasons", "assumptions", "required_next_steps"):
        if isinstance(readiness_norm.get(k), list):
            readiness_norm[k] = sorted([str(x) for x in readiness_norm.get(k) if str(x).strip()])

    if isinstance(readiness_norm.get("blockers"), list):
        blockers: List[Dict[str, Any]] = []
        for b in readiness_norm.get("blockers"):
            if isinstance(b, dict):
                blockers.append({"key": b.get("key"), "severity": b.get("severity")})
        readiness_norm["blockers"] = _sorted_list_of_dicts(blockers, key_fields=["key", "severity"])  # type: ignore[arg-type]

    gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
    gate_outcomes_norm = _canon_gate_outcomes_v2(gate_outcomes)

    measurement_ids_used = out.get("measurement_ids_used")
    if isinstance(measurement_ids_used, list):
        mids: List[int] = []
        for x in measurement_ids_used:
            try:
                mids.append(int(x))
            except Exception:
                continue
        measurement_ids_used_norm: List[int] = sorted(list(set(mids)))
    else:
        measurement_ids_used_norm = []

    return {
        "decision_state": out.get("decision_state"),
        "policy": {
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("policy_version"),
            "policy_semantics_hash": policy.get("policy_semantics_hash"),
            "policy_package_hash": policy.get("policy_package_hash"),
        },
        "measurement_ids_used": measurement_ids_used_norm,
        "gate_outcomes": gate_outcomes_norm,
        "readiness": readiness_norm,
    }


def compute_decision_output_hash(
    *,
    inputs_obj: Dict[str, Any],
    outputs_obj: Dict[str, Any],
) -> str:
    """Compute a deterministic hash over the *semantic* decision surface.

    This hash is designed to be stable across additive descriptive extensions
    (e.g., new SoE summaries, enriched risk flags) while remaining sensitive to
    actual decision outcome changes.
    """

    canon_inputs = canonical_inputs_for_integrity(inputs_obj or {})
    canon_outputs = canonical_outputs_for_decision_hash(outputs_obj or {})
    payload = {
        "inputs": canon_inputs,
        "decision": canon_outputs,
    }
    return _sha256_hex(_stable_json(payload))


def compute_decision_output_hash_v2(
    *,
    inputs_obj: Dict[str, Any],
    outputs_obj: Dict[str, Any],
) -> str:
    """Compute v2 semantic decision surface hash.

    v2 is the preferred verification surface for determining VERIFIED when
    policy hashes and evidence fingerprint are unchanged.
    """

    canon_outputs = canonical_outputs_for_decision_hash_v2(outputs_obj or {})
    payload = {
        "decision": canon_outputs,
    }
    return _sha256_hex(_stable_json(payload))
