from __future__ import annotations

from types import SimpleNamespace

from psi.services.sequence_annotation import annotate_sequence_for_editor


def test_sequence_annotation_structure_and_ordering() -> None:
    components = [
        SimpleNamespace(id=2, role="LC1", fasta="XYZ"),
        SimpleNamespace(id=1, role="HC1", fasta="ABCD"),
    ]
    domain_instances = [
        SimpleNamespace(component_id=1, start_idx=1, end_idx=3, domain_type="VH"),
        SimpleNamespace(component_id=2, start_idx=0, end_idx=2, domain_type="VL"),
    ]
    numbering_maps = [
        {"component_id": 1, "start_idx": 1, "labels_by_raw_index": ["H1", "H2"]},
        {"component_id": 2, "start_idx": 0, "labels_by_raw_index": ["L1", "L2"]},
    ]
    out = annotate_sequence_for_editor(
        components=components,
        domain_instances=domain_instances,
        numbering_maps=numbering_maps,
    )
    assert [c["component_role"] for c in out] == ["HC1", "LC1"]
    hc = out[0]
    lc = out[1]
    assert hc["sequence_length"] == 4
    assert hc["residues"][0]["region"] == "unassigned"
    assert hc["residues"][1]["region"] == "VH"
    assert hc["residues"][1]["numbering_label"] == "H1"
    assert hc["residues"][2]["numbering_label"] == "H2"
    assert lc["residues"][0]["region"] == "VL"
    assert lc["residues"][0]["numbering_label"] == "L1"


def test_sequence_annotation_is_deterministic_repeat_call() -> None:
    components = [SimpleNamespace(id=1, role="HC1", fasta="AB")]
    domain_instances = [SimpleNamespace(component_id=1, start_idx=0, end_idx=2, domain_type="VH")]
    a = annotate_sequence_for_editor(components=components, domain_instances=domain_instances, numbering_maps=[])
    b = annotate_sequence_for_editor(components=components, domain_instances=domain_instances, numbering_maps=[])
    assert a == b
