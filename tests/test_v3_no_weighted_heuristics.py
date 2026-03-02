from __future__ import annotations

from pathlib import Path


def test_no_weighted_heuristics_in_di_runtime_and_catalogs() -> None:
    root = Path(__file__).resolve().parents[1]
    targets = [
        root / "psi" / "services" / "di" / "shortlisting.py",
        root / "psi" / "services" / "di" / "compute.py",
        root / "psi" / "services" / "di" / "eval.py",
        root / "psi" / "core" / "di" / "catalogs" / "shortlisting_policy_v0_1.json",
    ]
    banned_literals = [
        "\"ranking_weights\"",
        "\"weight\":",
        "weighted_scoring\": true",
    ]
    for path in targets:
        txt = path.read_text(encoding="utf-8")
        for lit in banned_literals:
            assert lit not in txt, f"prohibited weighted heuristic token found in {path.name}: {lit}"

