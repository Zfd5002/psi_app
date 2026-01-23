from __future__ import annotations

"""Immunogenicity-style sequence analyses.

v1.1.8 scope:
  - lightweight MHC-I binding scan wrapper around MHCflurry (if installed)
  - no licenses, no GPU requirement (but tensorflow may still be heavy)

This module is intentionally small and optional:
  - If `mhcflurry` isn't installed or its models aren't downloaded, callers
    should catch exceptions and surface actionable instructions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from psi.core.fasta import normalize_aa_sequence


@dataclass(frozen=True)
class PeptideHit:
    peptide: str
    start: int  # 0-based
    end: int  # exclusive
    affinity_nm: float


def iter_peptides(seq: str, *, min_len: int = 8, max_len: int = 11) -> Iterable[Tuple[str, int, int]]:
    s = normalize_aa_sequence(seq)
    if not s:
        return []
    out: List[Tuple[str, int, int]] = []
    for k in range(int(min_len), int(max_len) + 1):
        if k <= 0 or k > len(s):
            continue
        for i in range(0, len(s) - k + 1):
            out.append((s[i : i + k], i, i + k))
    return out


def mhcflurry_predict_affinity_nm(
    *,
    peptides: List[str],
    allele: str,
) -> List[float]:
    """Return predicted affinities (nM) for the given peptides.

    Uses the MHCflurry Python API when available.
    """
    if not peptides:
        return []

    # MHCflurry 2.x tutorial recommends Class1PresentationPredictor. 
    # It includes affinity prediction and returns a DataFrame with an `affinity` column.
    try:
        from mhcflurry import Class1PresentationPredictor  # type: ignore

        predictor = Class1PresentationPredictor.load()
        df = predictor.predict(peptides=peptides, alleles=[allele], verbose=0)
        if "affinity" in df.columns:
            return [float(x) for x in df["affinity"].tolist()]
    except Exception:
        pass

    # Older API fallback
    from mhcflurry import Class1AffinityPredictor  # type: ignore

    predictor = Class1AffinityPredictor.load()
    df = predictor.predict_to_dataframe(peptides=peptides, allele=allele)
    # Column name differs across versions; check common candidates.
    for col in ("prediction", "mhcflurry_prediction", "affinity"):
        if col in df.columns:
            return [float(x) for x in df[col].tolist()]
    raise RuntimeError("Unexpected mhcflurry output: could not find affinity column")


def scan_mhci_binding(
    *,
    sequence: str,
    allele: str = "HLA-A0201",
    min_len: int = 8,
    max_len: int = 11,
    binder_threshold_nm: float = 500.0,
    top_k: int = 25,
    max_peptides: int = 20000,
) -> Dict[str, Any]:
    """Scan a protein sequence for predicted MHC-I binders.

    Returns a compact JSON payload:
      - counts
      - fraction_binders
      - top binders (lowest affinity)
      - settings
    """
    s = normalize_aa_sequence(sequence)
    peps = list(iter_peptides(s, min_len=min_len, max_len=max_len))
    truncated = False
    if len(peps) > int(max_peptides):
        peps = peps[: int(max_peptides)]
        truncated = True

    pep_strs = [p[0] for p in peps]
    affinities = mhcflurry_predict_affinity_nm(peptides=pep_strs, allele=allele)
    if len(affinities) != len(peps):
        raise RuntimeError("mhcflurry returned unexpected number of predictions")

    hits: List[PeptideHit] = []
    for (pep, start, end), aff in zip(peps, affinities):
        hits.append(PeptideHit(peptide=pep, start=start, end=end, affinity_nm=float(aff)))

    hits_sorted = sorted(hits, key=lambda h: h.affinity_nm)
    binders = [h for h in hits_sorted if h.affinity_nm < float(binder_threshold_nm)]

    top = hits_sorted[: int(top_k)]
    return {
        "status": "ok",
        "allele": allele,
        "peptide_len": {"min": int(min_len), "max": int(max_len)},
        "binder_threshold_nm": float(binder_threshold_nm),
        "n_peptides": int(len(hits_sorted)),
        "n_binders": int(len(binders)),
        "fraction_binders": float(len(binders) / max(1, len(hits_sorted))),
        "truncated": bool(truncated),
        "top_hits": [
            {"peptide": h.peptide, "start": h.start, "end": h.end, "affinity_nm": h.affinity_nm}
            for h in top
        ],
        "top_binders": [
            {"peptide": h.peptide, "start": h.start, "end": h.end, "affinity_nm": h.affinity_nm}
            for h in binders[: int(top_k)]
        ],
    }
