from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "psi" / "core" / "di" / "catalogs"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v3_catalog_immutability_locks_and_additive_version_surface() -> None:
    expected_locked = {
        "template_catalog_v0_1.json": "0bdd1ffacf0b55bde750bb1485e9923b5301849f3e4cb67e12837e6ff646e237",
        "ranking_policy_v0_1.json": "2294ac1c98197aaeed9e78cda324efa95ca645a9d3d14b339d216773e8ecd0a2",
        "comparability_policy_v0_1.json": "bc9e0605020b60d57a621ed6b6b1b8ce37c7973bddd9a488d318043a7b81d108",
    }
    for name, expected_hash in expected_locked.items():
        p = CATALOG_DIR / name
        assert p.is_file(), f"missing immutable catalog: {name}"
        assert _sha256_file(p) == expected_hash, f"immutable catalog hash mismatch: {name}"

    ranking_versions = sorted(p.name for p in CATALOG_DIR.glob("ranking_policy_v*.json"))
    assert ranking_versions == ["ranking_policy_v0_1.json", "ranking_policy_v0_2.json"]
    comparability_versions = sorted(p.name for p in CATALOG_DIR.glob("comparability_policy_v*.json"))
    assert comparability_versions == ["comparability_policy_v0_1.json"]
    template_versions = sorted(p.name for p in CATALOG_DIR.glob("template_catalog_v*.json"))
    assert template_versions == ["template_catalog_v0_1.json"]
