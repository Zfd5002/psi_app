from __future__ import annotations

from typing import Any

from psi.core.annotations import dedupe_features, detect_fc_region, detect_linker_spans
from psi.core.biochem import liability_sites
from psi.core.models import DomainInstance, MoleculeComponent
from psi.core.reference_features import detect_pdl1_features


def _confidence_from_mismatches(mismatches: int, length: int) -> float:
    if length <= 0:
        return 0.0
    mm = max(0, int(mismatches))
    return max(0.0, min(1.0, 1.0 - (mm / float(length))))


def domain_instances_by_component(*, domain_instances: list[DomainInstance]) -> dict[int, list[DomainInstance]]:
    out: dict[int, list[DomainInstance]] = {}
    for di in domain_instances or []:
        out.setdefault(int(di.component_id), []).append(di)
    return out


def build_feature_tracks(
    *,
    components: list[MoleculeComponent],
    di_by_component: dict[int, list[DomainInstance]],
    pdl1_allowed_mismatches: int,
) -> list[dict[str, Any]]:
    feature_tracks: list[dict[str, Any]] = []
    for c in components:
        seq = c.fasta or ""
        lanes = []

        dom_features = []
        for di in di_by_component.get(int(c.id), []):
            dom_features.append(
                {
                    "id": f"di:{di.id}",
                    "name": di.domain_type,
                    "feature_type": "domain_instance",
                    "start_idx": int(di.start_idx),
                    "end_idx": int(di.end_idx),
                    "source": di.source,
                    "status": di.status,
                    "method": di.method,
                    "tool_name": di.tool_name,
                    "tool_version": di.tool_version,
                    "meta": {"error": di.error} if di.error else {},
                }
            )
        if dom_features:
            lanes.append({"lane_name": "Domains", "features": dom_features})

        ref_features = []
        for rf in detect_pdl1_features(seq=seq, allowed_mismatches=int(pdl1_allowed_mismatches or 0)):
            ref_features.append(
                {
                    "id": f"ref:{c.id}:{rf.feature_type}:{rf.start_idx}:{rf.end_idx}:{rf.name}",
                    "name": rf.name,
                    "feature_type": rf.feature_type,
                    "start_idx": int(rf.start_idx),
                    "end_idx": int(rf.end_idx),
                    "source": "computed",
                    "status": "success",
                    "method": rf.method,
                    "tool_name": rf.tool_name,
                    "tool_version": rf.tool_version,
                    "parent_id": rf.parent_id,
                    "meta": rf.meta or {},
                }
            )
        if ref_features:
            lanes.append({"lane_name": "Reference matches", "features": ref_features})

        feature_tracks.append(
            {
                "component_id": int(c.id),
                "role": c.role,
                "sequence": seq,
                "length": len(seq),
                "lanes": lanes,
            }
        )
    return feature_tracks


def build_numbering_maps(
    *,
    components: list[MoleculeComponent],
    di_by_component: dict[int, list[DomainInstance]],
    numbering_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    numbering_maps: list[dict[str, Any]] = []
    payload_root = numbering_payload if isinstance(numbering_payload, dict) else {}
    for c in components:
        comp_id = int(c.id)
        comp_seq = c.fasta or ""
        for di in di_by_component.get(comp_id, []):
            if di.domain_type not in ["VH", "VL"]:
                continue
            start = int(di.start_idx)
            end = int(di.end_idx)
            dom_seq = comp_seq[start:end]
            payload = payload_root.get(di.domain_type) if isinstance(payload_root, dict) else None
            labels = payload.get("labels_by_raw_index") if isinstance(payload, dict) and payload else None
            numbering_maps.append(
                {
                    "component_id": comp_id,
                    "component_role": c.role,
                    "domain_type": di.domain_type,
                    "start_idx": start,
                    "end_idx": end,
                    "sequence": dom_seq,
                    "scheme": (payload.get("scheme") if isinstance(payload, dict) else None) or "kabat",
                    "tool_name": "abnumber",
                    "tool_version": "",
                    "cache_state": "success" if labels else ("pending" if payload_root.get("pending") else "missing"),
                    "labels_by_raw_index": labels or [],
                    "cdrs": (payload.get("cdrs") if isinstance(payload, dict) else None) or {},
                    "warnings": (payload.get("warnings") if isinstance(payload, dict) else None) or [],
                }
            )
    return numbering_maps


def build_viewer_v2_components(
    *,
    feature_tracks: list[dict[str, Any]],
    di_by_component: dict[int, list[DomainInstance]],
    numbering_payload: dict[str, Any] | None,
    pdl1_allowed_mismatches: int,
) -> list[dict[str, Any]]:
    viewer_v2_components = []
    payload_root = numbering_payload if isinstance(numbering_payload, dict) else {}
    for t in feature_tracks:
        length = int(t["length"])
        seq = t["sequence"]
        comp_id = int(t["component_id"])

        raw_labels = [str(i + 1) for i in range(length)]
        ab_labels = ["" for _ in range(length)]
        for di in di_by_component.get(comp_id, []):
            if di.domain_type not in ["VH", "VL"]:
                continue
            payload = payload_root.get(di.domain_type)
            if not payload:
                continue
            labels = payload.get("labels_by_raw_index") if isinstance(payload, dict) else None
            if not labels:
                continue
            start = int(di.start_idx)
            for i, lab in enumerate(labels):
                pos = start + i
                if 0 <= pos < length and lab:
                    ab_labels[pos] = str(lab)

        has_ab_numbering = any(bool(x) for x in ab_labels)
        features = []
        features.append(
            {
                "id": f"whole:{comp_id}",
                "name": "Full sequence",
                "group": "Sequence",
                "kind": "whole",
                "feature_type": "whole",
                "spans": [{"start": 0, "end": length}],
                "confidence": 1.0,
                "source": "always",
                "status": "success",
                "method": "identity",
                "tool_name": "",
                "tool_version": "",
                "meta": {},
                "parent_id": None,
            }
        )
        for di in di_by_component.get(comp_id, []):
            features.append(
                {
                    "id": f"di:{di.id}",
                    "name": di.domain_type,
                    "group": "Recognized regions",
                    "kind": "domain",
                    "feature_type": "domain",
                    "spans": [{"start": int(di.start_idx), "end": int(di.end_idx)}],
                    "confidence": 1.0,
                    "source": di.source,
                    "status": di.status,
                    "method": di.method,
                    "tool_name": di.tool_name,
                    "tool_version": di.tool_version,
                    "meta": {"error": di.error} if di.error else {},
                    "parent_id": None,
                }
            )
        fc = detect_fc_region(seq)
        if fc:
            features.append(
                {
                    "id": f"fc:{comp_id}:{fc.start}:{fc.end}",
                    "name": fc.name,
                    "group": "Recognized regions",
                    "kind": fc.kind,
                    "feature_type": "region",
                    "spans": [{"start": int(fc.start), "end": int(fc.end)}],
                    "confidence": float(fc.confidence),
                    "source": fc.source,
                    "status": "success",
                    "method": fc.method,
                    "tool_name": fc.tool_name,
                    "tool_version": fc.tool_version,
                    "meta": fc.meta or {},
                    "parent_id": None,
                }
            )
        for rf in detect_pdl1_features(seq=seq, allowed_mismatches=int(pdl1_allowed_mismatches or 0)):
            if rf.feature_type == "reference_match":
                mm = int(rf.meta.get("mismatches_total", 0))
                ln = int(rf.meta.get("reference_length", max(1, rf.end_idx - rf.start_idx)))
                conf = _confidence_from_mismatches(mm, ln)
            else:
                mm = int(rf.meta.get("mismatches", 0))
                ln = max(1, int(rf.end_idx - rf.start_idx))
                conf = _confidence_from_mismatches(mm, ln)
            features.append(
                {
                    "id": f"ref:{comp_id}:{rf.feature_type}:{rf.start_idx}:{rf.end_idx}:{rf.name}",
                    "name": rf.name,
                    "group": "Recognized regions",
                    "kind": "reference",
                    "feature_type": rf.feature_type,
                    "spans": [{"start": int(rf.start_idx), "end": int(rf.end_idx)}],
                    "confidence": conf,
                    "source": "computed",
                    "status": "success",
                    "method": rf.method,
                    "tool_name": rf.tool_name,
                    "tool_version": rf.tool_version,
                    "parent_id": rf.parent_id,
                    "meta": rf.meta or {},
                }
            )
        for lf in dedupe_features(detect_linker_spans(seq)):
            features.append(
                {
                    "id": f"linker:{comp_id}:{lf.start}:{lf.end}",
                    "name": lf.name,
                    "group": "Linkers / junctions",
                    "kind": lf.kind,
                    "feature_type": "linker",
                    "spans": [{"start": int(lf.start), "end": int(lf.end)}],
                    "confidence": float(lf.confidence),
                    "source": lf.source,
                    "status": "success",
                    "method": lf.method,
                    "tool_name": lf.tool_name,
                    "tool_version": lf.tool_version,
                    "meta": lf.meta or {},
                    "parent_id": None,
                }
            )
        for hit in liability_sites(seq):
            features.append(
                {
                    "id": f"motif:{comp_id}:{hit.get('type')}:{hit.get('start')}:{hit.get('end')}",
                    "name": hit.get("type", "motif"),
                    "group": "Motifs / liabilities",
                    "kind": "motif",
                    "feature_type": "motif",
                    "spans": [{"start": int(hit.get('start', 0)), "end": int(hit.get('end', 0))}],
                    "confidence": 1.0,
                    "source": "computed",
                    "status": "success",
                    "method": "liability_sites",
                    "tool_name": "psi_biochem",
                    "tool_version": "v1",
                    "meta": {k: v for k, v in hit.items() if k not in ('start', 'end')},
                    "parent_id": None,
                }
            )

        order = [
            "Sequence",
            "Recognized regions",
            "Linkers / junctions",
            "Engineering features",
            "Motifs / liabilities",
            "Diagnostics",
        ]
        grouped: dict[str, list[dict]] = {}
        for feat in features:
            grouped.setdefault(feat.get("group") or "Other", []).append(feat)
        annotations_groups = []
        for gname in order:
            items = grouped.get(gname, [])
            if not items:
                continue

            def _key(f):
                sp = (f.get("spans") or [{}])[0]
                return (int(sp.get("start", 0)), int(sp.get("end", 0)), str(f.get("name") or ""))

            items_sorted = sorted(items, key=_key)
            annotations_groups.append({"group": gname, "items": items_sorted})

        viewer_v2_components.append(
            {
                "component_id": comp_id,
                "role": t["role"],
                "sequence": seq,
                "length": length,
                "raw_labels": raw_labels,
                "ab_labels": ab_labels,
                "has_ab_numbering": has_ab_numbering,
                "features": features,
                "annotations_groups": annotations_groups,
            }
        )
    return viewer_v2_components
