from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import warnings

import yaml


_YAML_ENGINE_DEPRECATION_MSG = (
    "YAML DI engine is deprecated; JSON policy-as-data is canonical; removal timeline TBD."
)


def _warn_yaml_engine_deprecated() -> None:
    warnings.warn(_YAML_ENGINE_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)


def load_rules(path: str) -> Dict[str, Any]:
    _warn_yaml_engine_deprecated()
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass(frozen=True)
class EngineOutput:
    verdict: str
    confidence: int
    domain_scores: Dict[str, int]
    ceilings_triggered: List[str]
    blockers: List[str]
    what_would_change: List[str]


def compute_domain_score(
    rules: Dict[str, Any],
    domain: str,
    evidence_strength_by_type: Dict[str, int],
) -> Tuple[int, List[str]]:
    """Score 0-4 based on count of evidence types 'present' in the domain."""
    presence_threshold = int(rules.get("presence_threshold", 2))
    types = rules["domains"][domain]["evidence_types"]
    present = [t for t in types if evidence_strength_by_type.get(t, 0) >= presence_threshold]

    required_map = rules["scoring"]["required_present_count_by_score"]

    # Determine the highest score achieved.
    score = 0
    for s in sorted((int(k) for k in required_map.keys())):
        if len(present) >= int(required_map[str(s)]):
            score = s

    ceilings_triggered: List[str] = []
    for ceiling in rules.get("ceilings", []) or []:
        if ceiling.get("domain") != domain:
            continue
        missing_any = ceiling.get("if_missing_any", [])
        if any(evidence_strength_by_type.get(t, 0) < presence_threshold for t in missing_any):
            cap = int(ceiling.get("cap", score))
            if score > cap:
                ceilings_triggered.append(f"{domain} capped at {cap} (missing: {', '.join(missing_any)})")
                score = cap

    return score, ceilings_triggered


def run_engine(
    rules: Dict[str, Any],
    decision_key: str,
    evidence_strength_by_type: Dict[str, int],
) -> EngineOutput:
    decision_def = rules["decisions"].get(decision_key)
    if not decision_def:
        raise ValueError(f"Unknown decision key: {decision_key}")

    domain_scores: Dict[str, int] = {}
    ceilings_triggered: List[str] = []

    for domain in rules["domains"].keys():
        s, ceilings = compute_domain_score(rules, domain, evidence_strength_by_type)
        domain_scores[domain] = s
        ceilings_triggered.extend(ceilings)

    blockers: List[str] = []
    for hs in rules.get("hard_stops", []) or []:
        et = hs.get("evidence_type")
        trig = int(hs.get("triggers_if_strength_gte", 3))
        if et in (decision_def.get("hard_stops") or []) and evidence_strength_by_type.get(et, 0) >= trig:
            blockers.append(f"Hard stop: {et} (strength >= {trig})")

    meets = True
    for domain, min_score in (decision_def.get("min_domain_scores") or {}).items():
        if domain_scores.get(domain, 0) < int(min_score):
            meets = False

    if blockers:
        verdict = "BLOCKED"
    elif meets:
        verdict = "PASS"
    else:
        verdict = "HOLD"

    # Confidence is a simple heuristic: average of required domains, adjusted down for ceilings.
    req_domains = list((decision_def.get("min_domain_scores") or {}).keys())
    avg = 0
    if req_domains:
        avg = int(round(sum(domain_scores.get(d, 0) for d in req_domains) / len(req_domains)))
    confidence = max(0, min(4, avg - (1 if ceilings_triggered else 0) - (2 if blockers else 0)))

    what: List[str] = []
    if verdict != "PASS":
        presence_threshold = int(rules.get("presence_threshold", 2))
        for domain, min_score in (decision_def.get("min_domain_scores") or {}).items():
            if domain_scores.get(domain, 0) >= int(min_score):
                continue
            types = rules["domains"][domain]["evidence_types"]
            missing_present = [t for t in types if evidence_strength_by_type.get(t, 0) < presence_threshold]
            if missing_present:
                what.append(f"Raise {domain} by adding/strengthening: {', '.join(missing_present[:3])}")

    if blockers:
        what.append("Resolve hard stop evidence or scope it appropriately.")

    return EngineOutput(
        verdict=verdict,
        confidence=confidence,
        domain_scores=domain_scores,
        ceilings_triggered=ceilings_triggered,
        blockers=blockers,
        what_would_change=what,
    )


def run_decision(rules: Dict[str, Any], decision_key: str, evidence_rows: List[Any]) -> Dict[str, Any]:
    """High-level helper used by the web app.

    - Computes max strength per evidence_type in-scope.
    - Tracks which Evidence IDs were used (one per evidence_type: the max-strength row).
    - Returns a JSON-serializable dict for snapshot storage.
    """
    _warn_yaml_engine_deprecated()
    strength_by_type: Dict[str, int] = {}
    id_by_type: Dict[str, int] = {}

    # Pick the strongest evidence per type (tie-breaker: newest by id).
    for ev in evidence_rows:
        et = getattr(ev, "evidence_type", None)
        if not et:
            continue
        s = int(getattr(ev, "strength", 0) or 0)
        cur = strength_by_type.get(et)
        if cur is None or s > cur or (s == cur and int(getattr(ev, "id", 0)) > int(id_by_type.get(et, 0))):
            strength_by_type[et] = s
            id_by_type[et] = int(getattr(ev, "id", 0))

    out = run_engine(rules, decision_key, strength_by_type)

    # JSON shape used in decision report templates
    evidence_ids_used = sorted(set(id_by_type.values()))
    evidence_by_type = {
        et: {"evidence_id": id_by_type[et], "strength": strength_by_type[et]}
        for et in sorted(id_by_type.keys())
    }

    return {
        "decision_key": decision_key,
        "verdict": out.verdict,
        "confidence": out.confidence,
        "domain_scores": out.domain_scores,
        "ceilings_triggered": out.ceilings_triggered,
        "blockers": out.blockers,
        "what_would_change": out.what_would_change,
        "evidence_by_type": evidence_by_type,
        "evidence_ids_used": evidence_ids_used,
    }
