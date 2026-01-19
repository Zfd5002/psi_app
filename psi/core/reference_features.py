from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from psi.core.fasta import normalize_aa_sequence
from psi.core.reference_matching import find_best_substitution_match


# --- PD-L1 (human) reference sequences ---

PDL1_FULL_HUMAN_RAW = (
    "MRIFAVFIFMTYWHLLNAFTVTVPKDLYVVEYGSNMTIECKFPVEKQLDLAALIVYWEMEDKNIIQFVHGEEDLKVQHSSYRQRARLLKDQLSLGNAALQITDVKLQDAGVYRCMISYGGADYKRITVKVNAPYNKINQRILVVDPVTSEHELTCQAEGYPKAEVIWTSSDHQVLSGKTTTTNSKREEKLFNVTSTLRINTTTNEIFYCTFRRLDPEENHTAELV"
)

PDL1_VAR_SUBDOMAIN_RAW = (
    "FTVTVPKDLYVVEYGSNMTIECKFPVEKQLDLAALIVYWEMEDKNIIQFVHGEEDLKVQHSSYRQRARLLKDQLSLGNAALQITDVKLQDAGVYRCMISYGGADYKRIT"
)

PDL1_CONST_SUBDOMAIN_RAW = (
    "PYNKINQRILVVDPVTSEHELTCQAEGYPKAEVIWTSSDHQVLSGKTTTTNSKREEKLFNVTSTLRINTTTNEIFYCTFRRLDPEENHTAELV"
)

PDL1_FULL_HUMAN = normalize_aa_sequence(PDL1_FULL_HUMAN_RAW)
PDL1_VAR_SUBDOMAIN = normalize_aa_sequence(PDL1_VAR_SUBDOMAIN_RAW)
PDL1_CONST_SUBDOMAIN = normalize_aa_sequence(PDL1_CONST_SUBDOMAIN_RAW)


def _offset_or_raise(haystack: str, needle: str, name: str) -> int:
    idx = haystack.find(needle)
    if idx < 0:
        raise ValueError(f"{name} not found within PD-L1 full reference")
    return idx


# Offsets within the PD-L1 full reference (computed once).
PDL1_VAR_OFFSET = _offset_or_raise(PDL1_FULL_HUMAN, PDL1_VAR_SUBDOMAIN, "PD-L1 VAR subdomain")
PDL1_CONST_OFFSET = _offset_or_raise(PDL1_FULL_HUMAN, PDL1_CONST_SUBDOMAIN, "PD-L1 CONST subdomain")


@dataclass(frozen=True)
class ReferenceFeature:
    name: str
    feature_type: str  # e.g., reference_match, reference_subdomain
    start_idx: int
    end_idx: int
    tool_name: str
    tool_version: str
    method: str
    meta: dict
    parent_id: Optional[str] = None


def detect_pdl1_features(*, seq: str, allowed_mismatches: int) -> list[ReferenceFeature]:
    """Detect PD-L1 inside a larger chain using substitution-only matching.

    Returns a list of ReferenceFeature objects: parent PD-L1 full match plus VAR/CONST children.
    """

    s = normalize_aa_sequence(seq)
    if not s:
        return []

    m = find_best_substitution_match(seq=s, ref=PDL1_FULL_HUMAN, reference_name="PD-L1 (human)")
    if not m:
        return []

    if m.mismatches > int(allowed_mismatches or 0):
        return []

    tool_name = "psi_refscan"
    tool_version = "v1"
    method = "hamming_window"

    parent_id = f"pdl1:{m.start_idx}:{m.end_idx}"

    features: list[ReferenceFeature] = []
    features.append(
        ReferenceFeature(
            name="PD-L1 (human)",
            feature_type="reference_match",
            start_idx=m.start_idx,
            end_idx=m.end_idx,
            tool_name=tool_name,
            tool_version=tool_version,
            method=method,
            meta={
                "allowed_mismatches": int(allowed_mismatches or 0),
                "mismatches_total": int(m.mismatches),
                "reference_length": int(m.ref_length),
            },
            parent_id=None,
        )
    )

    # Child subdomains (fixed offsets within the PD-L1 reference)
    var_start = m.start_idx + PDL1_VAR_OFFSET
    var_end = var_start + len(PDL1_VAR_SUBDOMAIN)
    const_start = m.start_idx + PDL1_CONST_OFFSET
    const_end = const_start + len(PDL1_CONST_SUBDOMAIN)

    # mismatch breakdown (optional, cheap)
    def _count_mm(a: str, b: str) -> int:
        mm = 0
        for i in range(len(a)):
            if a[i] != b[i]:
                mm += 1
        return mm

    window = s[m.start_idx : m.end_idx]
    var_mm = _count_mm(window[PDL1_VAR_OFFSET : PDL1_VAR_OFFSET + len(PDL1_VAR_SUBDOMAIN)], PDL1_VAR_SUBDOMAIN)
    const_mm = _count_mm(
        window[PDL1_CONST_OFFSET : PDL1_CONST_OFFSET + len(PDL1_CONST_SUBDOMAIN)],
        PDL1_CONST_SUBDOMAIN,
    )

    features.append(
        ReferenceFeature(
            name="PD-L1 VAR",
            feature_type="reference_subdomain",
            start_idx=var_start,
            end_idx=var_end,
            tool_name=tool_name,
            tool_version=tool_version,
            method=method,
            meta={"mismatches": int(var_mm)},
            parent_id=parent_id,
        )
    )
    features.append(
        ReferenceFeature(
            name="PD-L1 CONST",
            feature_type="reference_subdomain",
            start_idx=const_start,
            end_idx=const_end,
            tool_name=tool_name,
            tool_version=tool_version,
            method=method,
            meta={"mismatches": int(const_mm)},
            parent_id=parent_id,
        )
    )

    return features
