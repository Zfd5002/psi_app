from __future__ import annotations

from psi.services.v3_ranking import build_ranking_surface, load_ranking_policy_v0_2


def test_ranking_tie_breaker_policy_driven_and_deterministic():
    policy = load_ranking_policy_v0_2()
    policy["enabled"] = True
    ents = [
        {"entity_type": "molecule", "entity_id": 2, "stable_sort_key": "M-B", "criteria_hits": []},
        {"entity_type": "molecule", "entity_id": 1, "stable_sort_key": "M-A", "criteria_hits": []},
    ]
    out1 = build_ranking_surface(entities=ents, policy=policy)
    out2 = build_ranking_surface(entities=list(reversed(ents)), policy=policy)
    assert [e["entity_id"] for e in out1["entities"]] == [1, 2]
    assert [e["entity_id"] for e in out1["entities"]] == [e["entity_id"] for e in out2["entities"]]
    assert out1["tie_break_keys"] == ["stable_sort_key", "entity_id"]
    assert out1["entities"][0]["tie_break_explanation"]["keys"] == ["stable_sort_key", "entity_id"]
    assert out1["entities"][0]["tie_break_explanation"]["key_values"]["stable_sort_key"] == "M-A"
    assert out1["explanation_trace_version"] == "v0.1"
    assert out1["entities"][0]["reason_trail"][0]["policy_rule_id"] == "high_severity_risk_present"
    assert isinstance(out1["entities"][0]["reason_trail"][0]["applied"], bool)


def test_ranking_policy_has_no_weights_and_has_tie_break_contract():
    policy = load_ranking_policy_v0_2()
    method = policy.get("method") if isinstance(policy.get("method"), dict) else {}
    assert "weights" not in method
    tie = method.get("tie_break_contract") if isinstance(method.get("tie_break_contract"), dict) else {}
    assert tie.get("deterministic_only") is True
    assert tie.get("numeric_scoring_allowed") is False
