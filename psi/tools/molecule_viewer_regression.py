from __future__ import annotations

from types import SimpleNamespace

from psi.services.molecule_viewer import (
    build_feature_tracks,
    build_numbering_maps,
    build_viewer_v2_components,
    domain_instances_by_component,
)


def _component(**kwargs):
    return SimpleNamespace(**kwargs)


def _domain_instance(**kwargs):
    return SimpleNamespace(**kwargs)


def main() -> int:
    components = [
        _component(id=1, role="HC", fasta="EVQLVESGGGLVQPGGSLRLSCAASGFTFSSYAMSWVRQAPGKGLEW"),
        _component(id=2, role="LC", fasta="DIQMTQSPSSLSASVGDRVTITCRASQSI"),
    ]
    domain_instances = [
        _domain_instance(
            id=10,
            component_id=1,
            domain_type="VH",
            start_idx=0,
            end_idx=20,
            source="computed",
            status="success",
            method="test",
            tool_name="fixture",
            tool_version="v1",
            error=None,
        )
    ]
    numbering_payload = {
        "VH": {
            "scheme": "kabat",
            "labels_by_raw_index": [str(i + 1) for i in range(20)],
            "cdrs": {},
            "warnings": [],
        }
    }

    di_by_component = domain_instances_by_component(domain_instances=domain_instances)
    assert sorted(di_by_component.keys()) == [1]
    feature_tracks = build_feature_tracks(
        components=components,
        di_by_component=di_by_component,
        pdl1_allowed_mismatches=1,
    )
    assert [int(t["component_id"]) for t in feature_tracks] == [1, 2]
    assert feature_tracks[0]["lanes"][0]["lane_name"] == "Domains"

    numbering_maps = build_numbering_maps(
        components=components,
        di_by_component=di_by_component,
        numbering_payload=numbering_payload,
    )
    assert len(numbering_maps) == 1
    assert numbering_maps[0]["domain_type"] == "VH"
    assert numbering_maps[0]["cache_state"] == "success"

    viewer = build_viewer_v2_components(
        feature_tracks=feature_tracks,
        di_by_component=di_by_component,
        numbering_payload=numbering_payload,
        pdl1_allowed_mismatches=1,
    )
    assert [int(v["component_id"]) for v in viewer] == [1, 2]
    assert all(isinstance(v.get("annotations_groups"), list) for v in viewer)
    assert all((v.get("raw_labels") or [])[0] == "1" for v in viewer if v.get("raw_labels"))
    print("OK molecule_viewer_regression")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
