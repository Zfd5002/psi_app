from __future__ import annotations

from typing import Dict

from .fasta import normalize_aa_sequence


# Average residue masses (Da) for polypeptide (without water) based on common tables.
AA_MASS: Dict[str, float] = {
    "A": 71.0788,
    "R": 156.1875,
    "N": 114.1038,
    "D": 115.0886,
    "C": 103.1388,
    "E": 129.1155,
    "Q": 128.1307,
    "G": 57.0519,
    "H": 137.1411,
    "I": 113.1594,
    "L": 113.1594,
    "K": 128.1741,
    "M": 131.1926,
    "F": 147.1766,
    "P": 97.1167,
    "S": 87.0782,
    "T": 101.1051,
    "W": 186.2132,
    "Y": 163.1760,
    "V": 99.1326,
}


# pKa values (approx) for pI estimate
PKA_NTERM = 9.69
PKA_CTERM = 2.34
PKA_SIDE = {
    "C": 8.33,
    "D": 3.86,
    "E": 4.25,
    "H": 6.00,
    "K": 10.53,
    "R": 12.48,
    "Y": 10.07,
}


def aa_composition(seq: str) -> Dict[str, int]:
    s = normalize_aa_sequence(seq)
    comp = {aa: 0 for aa in AA_MASS.keys()}
    other = 0
    for ch in s:
        if ch in comp:
            comp[ch] += 1
        else:
            other += 1
    if other:
        comp["X"] = other
    return comp


def sequence_length(seq: str) -> int:
    return len(normalize_aa_sequence(seq))


def molecular_weight_da(seq: str) -> float:
    """Average molecular weight in Daltons.

    Uses average residue masses + water (18.01528) for termini.
    Unknown residues contribute 0.
    """
    s = normalize_aa_sequence(seq)
    if not s:
        return 0.0
    mass = 18.01528  # water
    for ch in s:
        mass += AA_MASS.get(ch, 0.0)
    return mass


def cysteine_count(seq: str) -> int:
    return aa_composition(seq).get("C", 0)


def extinction_coefficient_a280(seq: str) -> Dict[str, int | float]:
    """Compute A280 extinction coefficient (M^-1 cm^-1) for reduced/oxidized.

    Reduced: counts all Cys as free thiols (0 contribution) per common convention.
    Oxidized: assumes all Cys form disulfides (pairs) contributing 125 each pair.
    """
    comp = aa_composition(seq)
    nW = comp.get("W", 0)
    nY = comp.get("Y", 0)
    nC = comp.get("C", 0)
    reduced = 5500 * nW + 1490 * nY
    disulfides = nC // 2
    oxidized = reduced + 125 * disulfides
    return {
        "trp": nW,
        "tyr": nY,
        "cys": nC,
        "extinction_reduced": float(reduced),
        "extinction_oxidized": float(oxidized),
        "assumed_disulfides": int(disulfides),
    }


def _net_charge_at_pH(seq: str, pH: float) -> float:
    comp = aa_composition(seq)

    # N-terminus (basic)
    pos = 1.0 / (1.0 + 10 ** (pH - PKA_NTERM))

    # C-terminus (acidic)
    neg = 1.0 / (1.0 + 10 ** (PKA_CTERM - pH))

    # basic side chains
    for aa, pka in (("K", PKA_SIDE["K"]), ("R", PKA_SIDE["R"]), ("H", PKA_SIDE["H"])):
        n = comp.get(aa, 0)
        pos += n * (1.0 / (1.0 + 10 ** (pH - pka)))

    # acidic side chains
    for aa, pka in (("D", PKA_SIDE["D"]), ("E", PKA_SIDE["E"]), ("C", PKA_SIDE["C"]), ("Y", PKA_SIDE["Y"])):
        n = comp.get(aa, 0)
        neg += n * (1.0 / (1.0 + 10 ** (pka - pH)))

    return pos - neg


def theoretical_pI(seq: str) -> float:
    """Estimate pI using a simple bisection on net charge."""
    s = normalize_aa_sequence(seq)
    if not s:
        return 0.0
    lo, hi = 0.0, 14.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        charge = _net_charge_at_pH(s, mid)
        if charge > 0:
            lo = mid
        else:
            hi = mid
    return float((lo + hi) / 2.0)


def instability_index(seq: str) -> float:
    """Compute the Guruprasad instability index.

    Note: This is a simplified implementation using a standard dipeptide table.
    """
    s = normalize_aa_sequence(seq)
    if not s:
        return 0.0
    try:
        from Bio.SeqUtils.ProtParam import ProteinAnalysis  # type: ignore

        return float(ProteinAnalysis(s).instability_index())
    except Exception:
        # Fallback: very rough proxy (higher gly/pro tends to be destabilizing) –
        # keep stable and deterministic without extra deps.
        comp = aa_composition(s)
        n = len(s)
        if n == 0:
            return 0.0
        return float(100.0 * (comp.get("G", 0) + comp.get("P", 0)) / n)


def basic_developability_proxies(seq: str) -> Dict[str, float]:
    """A small set of always-on, non-model-based proxies."""
    s = normalize_aa_sequence(seq)
    if not s:
        return {
            "net_charge_pH7": 0.0,
            "aromatic_fraction": 0.0,
            "hydrophobic_fraction": 0.0,
        }
    comp = aa_composition(s)
    n = len(s)
    arom = comp.get("F", 0) + comp.get("W", 0) + comp.get("Y", 0)
    hyd = sum(comp.get(x, 0) for x in ["A", "V", "I", "L", "M", "F", "W", "Y", "P"])
    return {
        "net_charge_pH7": float(_net_charge_at_pH(s, 7.0)),
        "aromatic_fraction": float(arom / n),
        "hydrophobic_fraction": float(hyd / n),
    }


def developability_risk_heuristics(seq: str) -> dict:
    """License-safe, CPU-cheap developability heuristics.

    This is intentionally *not* a trained model. It is meant to:
      - run quickly on low-powered machines
      - be deterministic and explainable
      - provide a compact "risk summary" for UI triage

    Output schema is stable JSON.
    """

    s = normalize_aa_sequence(seq)
    if not s:
        return {
            "overall": "unknown",
            "score": 0,
            "flags": [],
            "metrics": {},
        }

    proxies = basic_developability_proxies(s)
    motifs = motif_heuristics(s)
    cys = cysteine_count(s)
    instab = instability_index(s)

    flags: list[str] = []
    score = 0

    # Hydrophobicity fraction (very rough proxy for aggregation / stickiness)
    hyd = float(proxies.get("hydrophobic_fraction", 0.0))
    if hyd >= 0.48:
        flags.append("high_hydrophobic_fraction")
        score += 3
    elif hyd >= 0.45:
        flags.append("moderate_hydrophobic_fraction")
        score += 2
    elif hyd >= 0.42:
        score += 1

    # Net charge at pH7 (extremes can correlate with solubility / viscosity issues)
    netq = float(proxies.get("net_charge_pH7", 0.0))
    if abs(netq) >= 25:
        flags.append("extreme_net_charge_pH7")
        score += 2
    elif abs(netq) >= 18:
        flags.append("high_net_charge_pH7")
        score += 1

    # Instability index (protein-level proxy)
    if instab >= 55:
        flags.append("high_instability_index")
        score += 2
    elif instab >= 45:
        flags.append("moderate_instability_index")
        score += 1

    # Liability motifs
    n_gly = int(motifs.get("n_gly_motifs", 0))
    if n_gly >= 2:
        flags.append("multiple_n_gly_motifs")
        score += 2
    elif n_gly == 1:
        flags.append("n_gly_motif")
        score += 1

    deamid = int(motifs.get("deamidation_motifs", 0))
    if deamid >= 4:
        flags.append("many_deamidation_motifs")
        score += 2
    elif deamid >= 2:
        flags.append("some_deamidation_motifs")
        score += 1

    ox = int(motifs.get("oxidation_susceptible_residues", 0))
    if ox >= 20:
        flags.append("many_oxidation_susceptible_residues")
        score += 2
    elif ox >= 10:
        flags.append("some_oxidation_susceptible_residues")
        score += 1

    # Cysteines (unexpected extra cysteines can be a red flag depending on context)
    if cys >= 12:
        flags.append("high_cysteine_count")
        score += 1

    if score >= 8:
        overall = "high"
    elif score >= 4:
        overall = "moderate"
    else:
        overall = "low"

    return {
        "overall": overall,
        "score": int(score),
        "flags": flags,
        "metrics": {
            "hydrophobic_fraction": hyd,
            "net_charge_pH7": netq,
            "instability_index": float(instab),
            "n_gly_motifs": n_gly,
            "deamidation_motifs": deamid,
            "oxidation_susceptible_residues": ox,
            "cysteine_count": int(cys),
        },
    }


def motif_heuristics(seq: str) -> Dict[str, int]:
    """Detect simple sequence motifs relevant to liabilities."""
    s = normalize_aa_sequence(seq)
    # N-glycosylation: N-X-S/T where X != P
    n_gly = 0
    for i in range(len(s) - 2):
        if s[i] == "N" and s[i + 1] != "P" and s[i + 2] in ("S", "T"):
            n_gly += 1
    # deamidation: NG, NS, NT, NQ
    deamid = 0
    for motif in ("NG", "NS", "NT", "NQ"):
        deamid += s.count(motif)
    # oxidation: M, W (count)
    ox = s.count("M") + s.count("W")
    return {
        "n_gly_motifs": int(n_gly),
        "deamidation_motifs": int(deamid),
        "oxidation_susceptible_residues": int(ox),
    }


def liability_sites(seq: str) -> list[dict]:
    """Return positional liability sites for UI labeling.

    Indexing convention: 0-based positions, with spans half-open [start,end).

    This intentionally remains lightweight and always-on (FAST).
    """
    s = normalize_aa_sequence(seq)
    hits: list[dict] = []
    if not s:
        return hits

    # N-glycosylation: N-X-S/T where X != P
    for i in range(len(s) - 2):
        if s[i] == "N" and s[i + 1] != "P" and s[i + 2] in ("S", "T"):
            hits.append(
                {
                    "type": "N_glycosylation",
                    "start": i,
                    "end": i + 3,
                    "motif": s[i : i + 3],
                    "context": s[max(0, i - 5) : min(len(s), i + 8)],
                }
            )

    # Deamidation motifs: NG, NS, NT, NQ
    for motif in ("NG", "NS", "NT", "NQ"):
        start = 0
        while True:
            j = s.find(motif, start)
            if j == -1:
                break
            hits.append(
                {
                    "type": "deamidation",
                    "start": j,
                    "end": j + len(motif),
                    "motif": motif,
                    "context": s[max(0, j - 5) : min(len(s), j + 7)],
                }
            )
            start = j + 1

    # Oxidation susceptible residues: M, W
    for i, aa in enumerate(s):
        if aa in ("M", "W"):
            hits.append(
                {
                    "type": "oxidation_susceptible",
                    "start": i,
                    "end": i + 1,
                    "motif": aa,
                    "context": s[max(0, i - 5) : min(len(s), i + 6)],
                }
            )

    # Stable ordering for deterministic UI
    hits.sort(key=lambda x: (x.get("start", 0), x.get("type", "")))
    return hits
