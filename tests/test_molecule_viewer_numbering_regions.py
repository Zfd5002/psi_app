from __future__ import annotations

from types import SimpleNamespace

from psi.services.molecule_viewer import build_feature_tracks, build_viewer_v2_components, domain_instances_by_component


def _component(**kwargs):
    return SimpleNamespace(**kwargs)


def _domain_instance(**kwargs):
    return SimpleNamespace(**kwargs)


def _group_items_by_name(viewer_component: dict, group_name: str) -> list[dict]:
    groups = viewer_component.get("annotations_groups") or []
    for g in groups:
        if str(g.get("group") or "") == group_name:
            return list(g.get("items") or [])
    return []


def test_numbering_regions_surface_for_heavy_and_light_when_payload_present() -> None:
    components = [
        _component(id=1, role="HC1", fasta="ABCDEFG"),
        _component(id=2, role="LC1", fasta="HIJKLMN"),
    ]
    domain_instances = [
        _domain_instance(
            id=11,
            component_id=1,
            domain_type="VH",
            start_idx=0,
            end_idx=7,
            source="auto",
            status="success",
            method="anarci_domain_detection",
            tool_name="anarci",
            tool_version="vendored",
            error=None,
        ),
        _domain_instance(
            id=22,
            component_id=2,
            domain_type="VL",
            start_idx=0,
            end_idx=7,
            source="auto",
            status="success",
            method="anarci_domain_detection",
            tool_name="anarci",
            tool_version="vendored",
            error=None,
        ),
    ]
    numbering_payload = {
        "VH": {
            "scheme": "kabat",
            "labels_by_raw_index": ["H1", "H2", "H3", "H4", "H5", "H6", "H7"],
            "cdrs": {"FR1": "A", "CDR1": "B", "FR2": "C", "CDR2": "D", "FR3": "E", "CDR3": "F", "FR4": "G"},
            "warnings": [],
        },
        "VL": {
            "scheme": "kabat",
            "labels_by_raw_index": ["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
            "cdrs": {"FR1": "H", "CDR1": "I", "FR2": "J", "CDR2": "K", "FR3": "L", "CDR3": "M", "FR4": "N"},
            "warnings": [],
        },
    }

    di_by_component = domain_instances_by_component(domain_instances=domain_instances)
    tracks = build_feature_tracks(components=components, di_by_component=di_by_component, pdl1_allowed_mismatches=0)
    viewer = build_viewer_v2_components(
        feature_tracks=tracks,
        di_by_component=di_by_component,
        numbering_payload=numbering_payload,
        pdl1_allowed_mismatches=0,
    )

    expected_names = {"FR1", "CDR1", "FR2", "CDR2", "FR3", "CDR3", "FR4"}
    for comp in viewer:
        items = _group_items_by_name(comp, "Antibody regions")
        names = {str(i.get("name") or "") for i in items}
        assert names == expected_names


def test_numbering_regions_not_fabricated_without_complete_numbering_payload() -> None:
    components = [_component(id=1, role="HC1", fasta="ABCDEFG")]
    domain_instances = [
        _domain_instance(
            id=11,
            component_id=1,
            domain_type="VH",
            start_idx=0,
            end_idx=7,
            source="auto",
            status="success",
            method="anarci_domain_detection",
            tool_name="anarci",
            tool_version="vendored",
            error=None,
        )
    ]
    # Missing FR4 + inconsistent total length -> should not project FR/CDR layers.
    numbering_payload = {
        "VH": {
            "scheme": "kabat",
            "labels_by_raw_index": ["H1", "H2", "H3", "H4", "H5", "H6", "H7"],
            "cdrs": {"FR1": "A", "CDR1": "B", "FR2": "C", "CDR2": "D", "FR3": "E", "CDR3": "F"},
            "warnings": [],
        }
    }

    di_by_component = domain_instances_by_component(domain_instances=domain_instances)
    tracks = build_feature_tracks(components=components, di_by_component=di_by_component, pdl1_allowed_mismatches=0)
    viewer = build_viewer_v2_components(
        feature_tracks=tracks,
        di_by_component=di_by_component,
        numbering_payload=numbering_payload,
        pdl1_allowed_mismatches=0,
    )

    assert len(viewer) == 1
    assert _group_items_by_name(viewer[0], "Antibody regions") == []
    assert _group_items_by_name(viewer[0], "Recognized regions")

