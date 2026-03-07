from __future__ import annotations

from typing import Any

from psi.core.models import DomainInstance, MoleculeComponent


def _numbering_by_component(numbering_maps: list[dict[str, Any]] | None) -> dict[int, dict[int, str]]:
    out: dict[int, dict[int, str]] = {}
    for nm in numbering_maps or []:
        if not isinstance(nm, dict):
            continue
        comp_id = int(nm.get("component_id") or 0)
        labels = nm.get("labels_by_raw_index") if isinstance(nm.get("labels_by_raw_index"), list) else []
        start_idx = int(nm.get("start_idx") or 0)
        if comp_id <= 0 or not labels:
            continue
        by_pos = out.setdefault(comp_id, {})
        for i, lab in enumerate(labels):
            if not lab:
                continue
            raw_pos_1based = int(start_idx + i + 1)
            by_pos[raw_pos_1based] = str(lab)
    return out


def _region_maps(domain_instances: list[DomainInstance]) -> dict[int, list[tuple[int, int, str]]]:
    out: dict[int, list[tuple[int, int, str]]] = {}
    for di in sorted(
        domain_instances or [],
        key=lambda d: (int(d.component_id or 0), int(d.start_idx or 0), int(d.end_idx or 0), str(d.domain_type or "")),
    ):
        cid = int(di.component_id or 0)
        if cid <= 0:
            continue
        out.setdefault(cid, []).append((int(di.start_idx), int(di.end_idx), str(di.domain_type or "")))
    return out


def annotate_sequence_for_editor(
    *,
    components: list[MoleculeComponent],
    domain_instances: list[DomainInstance],
    numbering_maps: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    numbering = _numbering_by_component(numbering_maps)
    region_spans = _region_maps(domain_instances)

    out: list[dict[str, Any]] = []
    for c in sorted(components or [], key=lambda x: (str(x.role or ""), int(x.id or 0))):
        seq = str(c.fasta or "")
        cid = int(c.id or 0)
        spans = region_spans.get(cid, [])
        residues: list[dict[str, Any]] = []
        for i, aa in enumerate(seq, start=1):
            region = "unassigned"
            idx0 = i - 1
            for start, end, label in spans:
                if start <= idx0 < end:
                    region = label or "unassigned"
                    break
            residues.append(
                {
                    "component_id": cid,
                    "component_role": str(c.role or ""),
                    "position": i,
                    "aa": str(aa),
                    "region": str(region),
                    "numbering_label": str(numbering.get(cid, {}).get(i, "")),
                    "feature_flags": [],
                }
            )
        out.append(
            {
                "component_id": cid,
                "component_role": str(c.role or ""),
                "sequence_length": len(seq),
                "residues": residues,
            }
        )
    return out
