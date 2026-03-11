from __future__ import annotations

from psi.web.routers import molecules as molecules_router


def _row(role: str, seq: str, cid: int) -> dict:
    return {"role": role, "sequence": seq, "component_id": cid, "annotations_groups": [], "length": len(seq)}


def test_identical_heavy_chains_collapse_to_one_with_label() -> None:
    rows = [_row("HC1", "AAA", 1), _row("HC2", "AAA", 2), _row("LC1", "BBB", 3), _row("LC2", "CCC", 4)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    roles = [str(r.get("role")) for r in out]
    assert roles == ["HC1", "LC1", "LC2"]
    assert out[0].get("display_role_label") == "Heavy Chain (HC1 = HC2)"


def test_identical_light_chains_collapse_to_one_with_label() -> None:
    rows = [_row("HC1", "AAA", 1), _row("HC2", "DDD", 2), _row("LC1", "BBB", 3), _row("LC2", "BBB", 4)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    roles = [str(r.get("role")) for r in out]
    assert roles == ["HC1", "HC2", "LC1"]
    assert out[-1].get("display_role_label") == "Light Chain (LC1 = LC2)"


def test_heavy_different_light_identical_keeps_two_hc_one_lc() -> None:
    rows = [_row("HC1", "AAA", 1), _row("HC2", "DDD", 2), _row("LC1", "BBB", 3), _row("LC2", "BBB", 4)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    roles = [str(r.get("role")) for r in out]
    assert roles.count("HC1") == 1 and roles.count("HC2") == 1 and roles.count("LC1") == 1 and "LC2" not in roles


def test_heavy_identical_light_different_keeps_one_hc_two_lc() -> None:
    rows = [_row("HC1", "AAA", 1), _row("HC2", "AAA", 2), _row("LC1", "BBB", 3), _row("LC2", "CCC", 4)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    roles = [str(r.get("role")) for r in out]
    assert roles.count("HC1") == 1 and "HC2" not in roles and roles.count("LC1") == 1 and roles.count("LC2") == 1


def test_single_light_chain_not_misleadingly_collapsed() -> None:
    rows = [_row("HC1", "AAA", 1), _row("HC2", "DDD", 2), _row("LC1", "BBB", 3)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    labels = [str(r.get("display_role_label") or "") for r in out]
    assert len(out) == 3
    assert "Light Chain (LC1 = LC2)" not in labels


def test_single_heavy_chain_not_misleadingly_collapsed() -> None:
    rows = [_row("HC1", "AAA", 1), _row("LC1", "BBB", 3), _row("LC2", "CCC", 4)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    labels = [str(r.get("display_role_label") or "") for r in out]
    assert len(out) == 3
    assert "Heavy Chain (HC1 = HC2)" not in labels


def test_non_identical_duplicated_chains_render_separately() -> None:
    rows = [_row("HC1", "AAA", 1), _row("HC2", "DDD", 2), _row("LC1", "BBB", 3), _row("LC2", "CCC", 4)]
    out = molecules_router._collapse_symmetric_viewer_components(rows)
    roles = [str(r.get("role")) for r in out]
    assert roles == ["HC1", "HC2", "LC1", "LC2"]
    labels = [str(r.get("display_role_label") or "") for r in out]
    assert "Heavy Chain (HC1 = HC2)" not in labels
    assert "Light Chain (LC1 = LC2)" not in labels
