from __future__ import annotations

"""Schema-free annotation producers for PSI Viewer v2.

These functions emit *features* as spans on a raw component sequence.
They are intentionally:
  - deterministic
  - local-first
  - fast (no heavy dependencies)

Indexing convention: 0-based positions with half-open spans [start, end).
"""

from dataclasses import dataclass
import re
from typing import Iterable, Optional

from psi.core.fasta import normalize_aa_sequence
from psi.core.reference_matching import find_best_substitution_match


@dataclass(frozen=True)
class SimpleFeature:
    """Minimal feature representation for UI payloads."""

    name: str
    kind: str  # whole, region, domain, mutation, motif, linker, reference, etc.
    start: int
    end: int
    confidence: float
    source: str
    method: str
    tool_name: str = ""
    tool_version: str = ""
    meta: Optional[dict] = None


_G4S_RE = re.compile(r"(?:GGGGS){2,}")


def detect_linker_spans(seq: str) -> list[SimpleFeature]:
    """Detect obvious (G4S)n-style linkers.

    Conservative by design: we only emit when a clear multi-repeat is present.
    """
    s = normalize_aa_sequence(seq)
    if not s:
        return []
    out: list[SimpleFeature] = []
    for m in _G4S_RE.finditer(s):
        out.append(
            SimpleFeature(
                name="(G4S)n linker",
                kind="linker",
                start=int(m.start()),
                end=int(m.end()),
                confidence=0.95,
                source="heuristic",
                method="regex",
                tool_name="psi_linker",
                tool_version="v1",
                meta={"pattern": "(GGGGS){2,}"},
            )
        )
    return out


# A reference-anchored Fc segment (human IgG1, CH2/CH3 core).
# This is used only for high-confidence anchoring to support simple region labels.
_IGG1_FC_CORE = normalize_aa_sequence(
    "VVVDVSHEDPEVKFNWYVDGVEVHNAKTKPREEQYNSTYRVVSVLTVLHQDWLNGKEYKCKVSNKALPAPIEKTISKAKGQPREPQVYTLPPSRDELTKNQVSLTCLVKGFYPSDIAVEWESNGQPENNYKTTPPVLDSDGSFFLYSKLTVDKSRWQQGNVFSCSVMHEALHNHYTQKSLSLSPGK"
)


def detect_fc_region(seq: str) -> Optional[SimpleFeature]:
    """Detect a likely IgG1 Fc core segment using substitution-only matching.

    Emits a single span if the match is very strong (high identity).
    """
    s = normalize_aa_sequence(seq)
    if not s or len(s) < len(_IGG1_FC_CORE):
        return None

    m = find_best_substitution_match(seq=s, ref=_IGG1_FC_CORE, reference_name="IgG1 Fc core")
    if not m:
        return None

    # Extremely conservative threshold to avoid misleading annotations.
    ident = 1.0 - (float(m.mismatches) / float(max(1, m.ref_length)))
    if ident < 0.95:
        return None

    return SimpleFeature(
        name="Fc (IgG1 core)",
        kind="region",
        start=int(m.start_idx),
        end=int(m.end_idx),
        confidence=float(max(0.0, min(1.0, ident))),
        source="computed",
        method="substitution_anchor",
        tool_name="psi_refscan",
        tool_version="v1",
        meta={"mismatches": int(m.mismatches), "ref_length": int(m.ref_length)},
    )


def dedupe_features(features: Iterable[SimpleFeature]) -> list[SimpleFeature]:
    """Deterministic de-duplication.

    Prefers higher confidence for identical (name, kind, start, end).
    """
    best: dict[tuple, SimpleFeature] = {}
    for f in features:
        k = (f.name, f.kind, int(f.start), int(f.end))
        cur = best.get(k)
        if cur is None or float(f.confidence) > float(cur.confidence):
            best[k] = f
    out = list(best.values())
    out.sort(key=lambda x: (int(x.start), int(x.end), x.kind, x.name))
    return out
