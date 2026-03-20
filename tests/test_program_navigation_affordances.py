from __future__ import annotations

from pathlib import Path


def test_molecule_detail_has_program_workspace_action() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "detail.html").read_text(
        encoding="utf-8"
    )
    assert "Open Program Workspace" in tpl
    assert "\"/programs/\" ~ molecule.program_id" in tpl


def test_batch_detail_has_program_workspace_action() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "batches" / "detail.html").read_text(
        encoding="utf-8"
    )
    assert "Open Program Workspace" in tpl
    assert "/programs/{{ molecule.program_id }}" in tpl


def test_molecule_detail_has_experiment_review_entry() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "detail.html").read_text(
        encoding="utf-8"
    )
    assert "View Experiment Results" in tpl
    assert "/molecules/\" ~ molecule.id ~ \"/results" in tpl


def test_molecule_surface_nav_has_split_links() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "partials" / "surface_nav.html").read_text(
        encoding="utf-8"
    )
    assert 'href="/molecules/{{ _sid }}"' in tpl
    assert "/molecules/{{ _sid }}/results" in tpl
    assert "/molecules/{{ _sid }}/sequence" in tpl
    assert "/molecules/{{ _sid }}/sequence-analysis" in tpl
    assert "/molecules/{{ _sid }}/governance" in tpl


def test_molecule_split_templates_hide_surface_chrome_nav() -> None:
    root = Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules"
    for name in ("detail.html", "results.html", "sequence.html", "governance.html"):
        tpl = (root / name).read_text(encoding="utf-8")
        assert "{% set hide_surface_local_nav = true %}" in tpl


def test_molecule_registry_has_split_surface_quick_links() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "list.html").read_text(
        encoding="utf-8"
    )
    assert "/molecules/{{ m.id }}/results" in tpl
    assert "/molecules/{{ m.id }}/sequence" in tpl
    assert "/molecules/{{ m.id }}/governance" in tpl


def test_molecule_sequence_template_includes_viewer_and_scripts() -> None:
    tpl = (Path(__file__).resolve().parents[1] / "psi" / "web" / "templates" / "molecules" / "sequence.html").read_text(
        encoding="utf-8"
    )
    assert "Sequence Analysis Handoff" in tpl
    assert "Open Full Sequence Analysis" in tpl
    assert "/molecules/{{ molecule.id }}/sequence-analysis" in tpl
    assert 'include "molecules/partials/sequence_viewer.html"' in tpl
    assert '/static/molecule_detail.js' in tpl
    assert 'id="molecule-detail-config"' in tpl


def test_molecule_sequence_analysis_template_has_locked_section_order() -> None:
    tpl = (
        Path(__file__).resolve().parents[1]
        / "psi"
        / "web"
        / "templates"
        / "molecules"
        / "sequence_analysis.html"
    ).read_text(encoding="utf-8")
    markers = [
        "1. Sequence Analysis Summary",
        "2. Physicochemical Core",
        "3. Amino Acid Composition",
        "4. Derived Composition Metrics",
        "5. Motif and Liability Summary",
        "6. Developability Proxies and Risk",
        "7. Component-Level Developability",
        "8. Assembly and Architecture Context",
        "9. Advanced Payloads (Raw)",
    ]
    idx = [tpl.index(m) for m in markers]
    assert idx == sorted(idx)


def test_sequence_viewer_partial_has_liability_bulk_controls() -> None:
    tpl = (
        Path(__file__).resolve().parents[1]
        / "psi"
        / "web"
        / "templates"
        / "molecules"
        / "partials"
        / "sequence_viewer.html"
    ).read_text(encoding="utf-8")
    assert 'data-action="viewer-bulk-highlight"' in tpl
    assert 'data-feature-name="oxidation_susceptible"' in tpl
    assert 'data-feature-name="deamidation"' in tpl
    assert 'data-feature-name="N_glycosylation"' in tpl
