from psi.web import ui_surfaces


def test_surface_descriptor_builders_are_deterministic() -> None:
    d = ui_surfaces.overview_surface(
        surface_key="portfolio_overview",
        surface_title="Portfolio Intelligence",
        surface_subtitle="Command surface",
        dominant_purpose="prioritization",
        local_nav=[ui_surfaces.nav_item("Summary", "#summary"), ui_surfaces.nav_item("Programs", "#programs")],
        archetype_labels=["Overview Page", "Prioritization Surface"],
        attention_mode="high",
        workflow_stage_emphasis="program prioritization",
        secondary_sections_collapsed_by_default=True,
    )
    assert d["surface_key"] == "portfolio_overview"
    assert d["surface_kind"] == "overview"
    assert d["surface_title"] == "Portfolio Intelligence"
    assert d["local_nav"][0]["label"] == "Summary"
    assert d["archetype_labels"] == ["Overview Page", "Prioritization Surface"]
    assert d["secondary_sections_collapsed_by_default"] is True


def test_nav_item_defaults() -> None:
    item = ui_surfaces.nav_item("Workflow", "/programs/1/workflow")
    assert item == {"label": "Workflow", "href": "/programs/1/workflow", "active": False}


def test_program_workflow_surface_includes_learning_nav_items() -> None:
    d = ui_surfaces.program_workflow_surface(program_id=4)
    labels = [str(x.get("label")) for x in d.get("local_nav", [])]
    assert "Recent Learning" in labels
    assert "Awaiting Interpretation" in labels
