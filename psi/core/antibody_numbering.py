from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .fasta import normalize_aa_sequence


SUPPORTED_SCHEMES = ["kabat", "imgt", "chothia"]


@dataclass
class NumberingResult:
    scheme: str
    chain_type: str  # VH | VL
    positions: Dict[str, str]  # position -> residue
    cdrs: Dict[str, Any]
    spans: Dict[str, Any]
    warnings: List[str]


def _abnumber_available() -> bool:
    try:
        import abnumber  # noqa: F401

        return True
    except Exception:
        return False


def number_variable_domain(seq: str, *, scheme: str = "kabat") -> Optional[NumberingResult]:
    """Number a VH/VL variable domain using abnumber (preferred).

    Returns None if numbering is unavailable.
    """
    s = normalize_aa_sequence(seq)
    if not s:
        return None
    scheme_l = (scheme or "kabat").lower()
    if scheme_l not in SUPPORTED_SCHEMES:
        scheme_l = "kabat"

    try:
        from abnumber import Chain  # type: ignore

        ch = Chain(s, scheme=scheme_l)
        ctype = "VH" if ch.chain_type == "H" else "VL"
        # position labels are already scheme-specific (including insertions)
        pos_map: Dict[str, str] = {str(p): aa for p, aa in ch.positions.items()}

        cdrs = {
            "CDR1": str(getattr(ch, "cdr1_seq", "") or ""),
            "CDR2": str(getattr(ch, "cdr2_seq", "") or ""),
            "CDR3": str(getattr(ch, "cdr3_seq", "") or ""),
            "FR1": str(getattr(ch, "fr1_seq", "") or ""),
            "FR2": str(getattr(ch, "fr2_seq", "") or ""),
            "FR3": str(getattr(ch, "fr3_seq", "") or ""),
            "FR4": str(getattr(ch, "fr4_seq", "") or ""),
        }

        # abnumber 0.4.x may not expose an explicit alignment object.
        # We compute a raw-index -> scheme-position-label mapping for UI alignment.
        labels_by_raw_index: List[str] = [""] * len(s)
        mapped: List[int] = []
        for i in range(len(s)):
            try:
                p = ch.get_position_by_raw_index(i)
            except Exception:
                p = None
            if p is not None:
                mapped.append(i)
                labels_by_raw_index[i] = str(p)

        spans = {}
        if mapped:
            spans = {
                "variable_start": int(min(mapped)),
                "variable_end": int(max(mapped) + 1),
            }

        warnings: List[str] = []
        if getattr(ch, "warnings", None):
            warnings.extend([str(w) for w in ch.warnings])

        res = NumberingResult(
            scheme=scheme_l,
            chain_type=ctype,
            positions=pos_map,
            cdrs=cdrs,
            spans=spans,
            warnings=warnings,
        )
        # Attach UI-friendly mapping without changing the public dataclass shape.
        # (This gets serialized into DomainArtifact payload by services/numbering.py.)
        setattr(res, "labels_by_raw_index", labels_by_raw_index)
        return res
    except Exception as e:
        # Graceful failure: treat as unavailable
        return NumberingResult(
            scheme=scheme_l,
            chain_type="unknown",
            positions={},
            cdrs={},
            spans={},
            warnings=[f"Numbering unavailable: {e}"],
        )
