from __future__ import annotations

from pathlib import Path

from psi.services.legacy_yaml_compat import load_rules_legacy_yaml
from psi.services.legacy_yaml_compat import run_decision_legacy_yaml
from psi.web.app import create_app


def test_create_app_boots_with_legacy_rules_path_state() -> None:
    app = create_app(base_dir=Path(__file__).resolve().parents[1])
    assert str(app.state.rules_path).endswith("psi_rules/psirules-0.1.0.yml")


def test_legacy_yaml_compat_load_and_run_round_trip(tmp_path: Path) -> None:
    rules_path = tmp_path / "rules.yml"
    rules_path.write_text(
        """
presence_threshold: 2
domains:
  efficacy:
    evidence_types: ["in_vitro"]
decisions:
  go:
    min_domain_scores:
      efficacy: 1
scoring:
  required_present_count_by_score:
    "1": 1
ceilings: []
hard_stops: []
""".strip(),
        encoding="utf-8",
    )
    rules = load_rules_legacy_yaml(str(rules_path))

    class _Ev:
        def __init__(self, evidence_id: int, evidence_type: str, strength: int):
            self.id = int(evidence_id)
            self.evidence_type = str(evidence_type)
            self.strength = int(strength)

    out = run_decision_legacy_yaml(
        rules,
        "go",
        [_Ev(1, "in_vitro", 3)],
    )
    assert str(out.get("decision_key") or "") == "go"
    assert "verdict" in out
    assert isinstance(out.get("evidence_ids_used"), list)
