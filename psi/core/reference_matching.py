from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from psi.core.fasta import normalize_aa_sequence


@dataclass(frozen=True)
class BestSubstitutionMatch:
    """Best (lowest-mismatch) same-length window match.

    Indexing: 0-based, half-open [start_idx, end_idx)
    """

    reference_name: str
    start_idx: int
    end_idx: int
    mismatches: int
    ref_length: int


def find_best_substitution_match(*, seq: str, ref: str, reference_name: str = "reference") -> Optional[BestSubstitutionMatch]:
    """Scan seq for the best substitution-only match to ref.

    Assumes no indels (fixed window length). Uses Hamming mismatch count.

    Returns None if seq or ref are empty, or if seq is shorter than ref.
    """

    s = normalize_aa_sequence(seq)
    r = normalize_aa_sequence(ref)
    if not s or not r:
        return None
    if len(s) < len(r):
        return None

    best_start = 0
    best_mismatches = len(r) + 1

    # O(n*m) is fine for typical protein lengths.
    window_len = len(r)
    for i in range(0, len(s) - window_len + 1):
        mm = 0
        # Early exit if already worse than current best.
        for j in range(window_len):
            if s[i + j] != r[j]:
                mm += 1
                if mm >= best_mismatches:
                    break
        if mm < best_mismatches:
            best_mismatches = mm
            best_start = i
            if best_mismatches == 0:
                break

    return BestSubstitutionMatch(
        reference_name=reference_name,
        start_idx=best_start,
        end_idx=best_start + len(r),
        mismatches=best_mismatches,
        ref_length=len(r),
    )
