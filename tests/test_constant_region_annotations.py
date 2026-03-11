from __future__ import annotations

from psi.core.annotations import _IGG1_FC_CORE
from psi.core.constant_regions import analyze_constant_regions
from psi.core.models import DomainArtifact, MoleculeComponent, Molecule, Program
from psi.core.utils import now_utc
from psi.services.constant_regions import get_constant_region_payload_for_components
from psi.services.molecule_viewer import build_viewer_v2_components
from psi.services.sequences import get_or_create_sequence_entity


def _hinge_positive_sequence() -> str:
    # Conservative hinge motif upstream of a high-confidence Fc-core anchor.
    return "EVQLQQSGAATHTCPPCPAPELLGGPSVFLFPPKPKD" + _IGG1_FC_CORE


def test_constant_region_hinge_detects_when_fc_anchored() -> None:
    out = analyze_constant_regions(seq=_hinge_positive_sequence())
    feats = list(out.get("features") or [])
    names = [str(f.get("name") or "") for f in feats if isinstance(f, dict)]
    assert "hinge" in names
    assert any(n.startswith("Fc (") for n in names)
    anchor = out.get("fc_anchor") if isinstance(out, dict) else None
    assert isinstance(anchor, dict)
    hinge = next(f for f in feats if str(f.get("name")) == "hinge")
    assert int(hinge.get("end") or 0) <= int(anchor.get("start") or 0)


def test_constant_region_hinge_not_emitted_without_cppc_upstream() -> None:
    seq = ("A" * 120) + _IGG1_FC_CORE
    out = analyze_constant_regions(seq=seq)
    feats = list(out.get("features") or [])
    assert not any(str(f.get("name") or "") == "hinge" for f in feats if isinstance(f, dict))


def test_constant_region_lala_detected_only_in_fc_anchored_window() -> None:
    seq = "M" * 200 + "LALA" + "EVQLQQSGAATHTCPPCPAPELLGGPSVFLFPPKPKD" + _IGG1_FC_CORE
    out = analyze_constant_regions(seq=seq)
    feats = list(out.get("features") or [])
    names = [str(f.get("name") or "") for f in feats if isinstance(f, dict)]
    assert "LALA" in names


def test_constant_region_lalapg_takes_precedence_over_lala_overlap() -> None:
    seq = "EVQLQQSGAATHTCPPCPAPELLGGPSVFLFPPKPKDLALAPG" + _IGG1_FC_CORE
    out = analyze_constant_regions(seq=seq)
    feats = [f for f in list(out.get("features") or []) if isinstance(f, dict)]
    names = [str(f.get("name") or "") for f in feats]
    assert "LALAPG" in names
    # Avoid duplicate overlapping LALA call when the longer motif is present.
    assert "LALA" not in names


def test_constant_region_motif_outside_fc_window_not_called() -> None:
    seq = "LALA" + ("A" * 240) + "EVQLQQSGAATHTCPPCPAPELLGGPSVFLFPPKPKD" + _IGG1_FC_CORE
    out = analyze_constant_regions(seq=seq)
    feats = list(out.get("features") or [])
    assert not any(str(f.get("name") or "") in {"LALA", "LALAPG"} for f in feats if isinstance(f, dict))


def test_constant_region_fc_species_human_high_confidence() -> None:
    seq = "EVQLQQSGAATHTCPPCPAPELLGGPSVFLFPPKPKD" + _IGG1_FC_CORE
    out = analyze_constant_regions(seq=seq)
    feats = [f for f in list(out.get("features") or []) if isinstance(f, dict)]
    names = [str(f.get("name") or "") for f in feats]
    assert "Fc (human)" in names


def test_constant_region_fc_species_uncertain_when_identity_is_low() -> None:
    core = list(_IGG1_FC_CORE)
    # Introduce deterministic substitutions while keeping Fc anchor above threshold.
    for i in (0, 5, 11, 17, 23, 29, 31, 37):
        core[i] = "A" if core[i] != "A" else "V"
    seq = "EVQLQQSGAATHTCPPCPAPELLGGPSVFLFPPKPKD" + "".join(core)
    out = analyze_constant_regions(seq=seq)
    feats = [f for f in list(out.get("features") or []) if isinstance(f, dict)]
    names = [str(f.get("name") or "") for f in feats]
    assert "Fc (species uncertain)" in names


def test_constant_region_payload_is_persisted_as_domain_artifact(mkdb) -> None:
    _, SessionTmp = mkdb()
    with SessionTmp() as db:
        now = now_utc()
        p = Program(name="CONST-REG", description="", created_at=now, updated_at=now)
        db.add(p)
        db.commit()
        db.refresh(p)

        m = Molecule(
            program_id=int(p.id),
            primary_id="CONST-REG-001",
            title="Const Regions",
            sequences="",
            molecule_format="IgG",
            heavy_compute_enabled=1,
            created_at=now,
            updated_at=now,
        )
        db.add(m)
        db.commit()
        db.refresh(m)

        seq = _hinge_positive_sequence()
        ent = get_or_create_sequence_entity(db, seq)
        c = MoleculeComponent(
            molecule_id=int(m.id),
            role="HC1",
            fasta=seq,
            sha256="x",
            sequence_entity_id=int(ent.id),
            created_at=now,
            updated_at=now,
        )
        db.add(c)
        db.commit()
        db.refresh(c)

        payload = get_constant_region_payload_for_components(db, components=[c])
        assert int(c.id) in payload
        feats = list((payload[int(c.id)] or {}).get("features") or [])
        assert any(str(f.get("name") or "") == "hinge" for f in feats if isinstance(f, dict))

        arts = (
            db.query(DomainArtifact)
            .filter(DomainArtifact.sequence_id == int(ent.id))
            .filter(DomainArtifact.artifact_type == "constant_region_annotations")
            .all()
        )
        assert arts
        assert any(str(a.status or "") == "success" for a in arts)


def test_viewer_projects_constant_region_payload_features() -> None:
    viewer = build_viewer_v2_components(
        feature_tracks=[{"component_id": 1, "role": "HC1", "sequence": "A" * 240, "length": 240, "lanes": []}],
        di_by_component={},
        numbering_payload={},
        constant_region_payload_by_component={
            1: {
                "features": [
                    {
                        "name": "hinge",
                        "group": "Recognized regions",
                        "kind": "region",
                        "feature_type": "region",
                        "start": 90,
                        "end": 104,
                        "confidence": 0.9,
                        "source": "computed",
                        "status": "success",
                        "method": "fc_anchor_cppc",
                        "tool_name": "psi_constant_regions",
                        "tool_version": "d138",
                        "meta": {"anchor_feature": "Fc (IgG1 core)"},
                    }
                ]
            }
        },
        pdl1_allowed_mismatches=0,
    )
    groups = list((viewer[0] or {}).get("annotations_groups") or [])
    rec = next(g for g in groups if str(g.get("group") or "") == "Recognized regions")
    names = {str(i.get("name") or "") for i in list(rec.get("items") or [])}
    assert "hinge" in names


def test_viewer_projects_engineering_constant_features() -> None:
    viewer = build_viewer_v2_components(
        feature_tracks=[{"component_id": 1, "role": "HC1", "sequence": "A" * 260, "length": 260, "lanes": []}],
        di_by_component={},
        numbering_payload={},
        constant_region_payload_by_component={
            1: {
                "features": [
                    {
                        "name": "LALAPG",
                        "group": "Engineering features",
                        "kind": "motif",
                        "feature_type": "motif",
                        "start": 120,
                        "end": 126,
                        "confidence": 0.95,
                        "source": "computed",
                        "status": "success",
                        "method": "fc_anchor_window_exact",
                        "tool_name": "psi_constant_regions",
                        "tool_version": "d138",
                        "meta": {},
                    }
                ]
            }
        },
        pdl1_allowed_mismatches=0,
    )
    groups = list((viewer[0] or {}).get("annotations_groups") or [])
    eng = next(g for g in groups if str(g.get("group") or "") == "Engineering features")
    names = {str(i.get("name") or "") for i in list(eng.get("items") or [])}
    assert "LALAPG" in names


def test_viewer_avoids_duplicate_legacy_fc_when_species_call_present() -> None:
    seq = _IGG1_FC_CORE
    viewer = build_viewer_v2_components(
        feature_tracks=[{"component_id": 1, "role": "HC1", "sequence": seq, "length": len(seq), "lanes": []}],
        di_by_component={},
        numbering_payload={},
        constant_region_payload_by_component={
            1: {
                "features": [
                    {
                        "name": "Fc (human-like)",
                        "group": "Recognized regions",
                        "kind": "region",
                        "feature_type": "region",
                        "start": 0,
                        "end": len(seq),
                        "confidence": 0.98,
                        "source": "computed",
                        "status": "success",
                        "method": "fc_anchor_identity",
                        "tool_name": "psi_constant_regions",
                        "tool_version": "d138",
                        "meta": {"identity_bucket": "moderate"},
                    }
                ]
            }
        },
        pdl1_allowed_mismatches=0,
    )
    groups = list((viewer[0] or {}).get("annotations_groups") or [])
    rec = next(g for g in groups if str(g.get("group") or "") == "Recognized regions")
    names = [str(i.get("name") or "") for i in list(rec.get("items") or [])]
    assert "Fc (human-like)" in names
    assert "Fc (IgG1 core)" not in names
