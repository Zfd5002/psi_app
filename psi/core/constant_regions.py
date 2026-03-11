from __future__ import annotations

"""Deterministic constant-region annotation helpers.

v1 scope is intentionally conservative:
  - hinge identification anchored to a high-confidence Fc core match
  - anchored LALA / LALAPG motif calls in Fc neighborhood
  - Fc species-like labeling with uncertainty handling
"""

from typing import Any

from psi.core.annotations import detect_fc_region
from psi.core.fasta import normalize_aa_sequence


def analyze_constant_regions(*, seq: str) -> dict[str, Any]:
    """Return conservative constant-region calls for a sequence.

    Output is schema-light and suitable for persistence in DomainArtifact.
    """
    s = normalize_aa_sequence(seq)
    if not s:
        return {"analysis_version": "d138", "features": [], "fc_anchor": None}

    fc = detect_fc_region(s)
    if not fc:
        return {"analysis_version": "d138", "features": [], "fc_anchor": None}

    out: dict[str, Any] = {
        "analysis_version": "d138",
        "features": [],
        "fc_anchor": {
            "start": int(fc.start),
            "end": int(fc.end),
            "confidence": float(fc.confidence),
            "method": str(fc.method),
            "tool_name": str(fc.tool_name),
            "tool_version": str(fc.tool_version),
            "meta": dict(fc.meta or {}),
        },
    }

    # Fc species-like call (conservative, uncertainty-aware).
    ref_len = int((fc.meta or {}).get("ref_length") or max(1, int(fc.end) - int(fc.start)))
    mismatches = int((fc.meta or {}).get("mismatches") or 0)
    ident = float(max(0.0, min(1.0, 1.0 - (mismatches / float(max(1, ref_len))))))
    if ident >= 0.99:
        species_label = "Fc (human)"
        bucket = "high"
    elif ident >= 0.97:
        species_label = "Fc (human-like)"
        bucket = "moderate"
    else:
        species_label = "Fc (species uncertain)"
        bucket = "low"
    out["features"].append(
        {
            "name": species_label,
            "group": "Recognized regions",
            "kind": "region",
            "feature_type": "region",
            "start": int(fc.start),
            "end": int(fc.end),
            "confidence": ident,
            "source": "computed",
            "status": "success",
            "method": "fc_anchor_identity",
            "tool_name": "psi_constant_regions",
            "tool_version": "d138",
            "meta": {
                "reference": "IgG1 Fc core",
                "identity": ident,
                "identity_bucket": bucket,
                "mismatches": mismatches,
                "ref_length": ref_len,
            },
        }
    )

    # Conservative hinge call:
    # - only when Fc is confidently anchored
    # - only when canonical CPPC motif exists in a bounded upstream window
    lo = max(0, int(fc.start) - 90)
    hi = int(fc.start)
    upstream = s[lo:hi]
    motif = "CPPC"
    rel = upstream.rfind(motif)
    if rel >= 0:
        motif_start = int(lo + rel)
        motif_end = int(motif_start + len(motif))
        hinge_start = int(max(lo, motif_start - 3))
        hinge_end = int(min(hi, motif_end + 7))
        if hinge_end > hinge_start:
            out["features"].append(
                {
                    "name": "hinge",
                    "group": "Recognized regions",
                    "kind": "region",
                    "feature_type": "region",
                    "start": hinge_start,
                    "end": hinge_end,
                    "confidence": float(max(0.0, min(1.0, min(float(fc.confidence), 0.90)))),
                    "source": "computed",
                    "status": "success",
                    "method": "fc_anchor_cppc",
                    "tool_name": "psi_constant_regions",
                    "tool_version": "d138",
                    "meta": {
                        "anchor_feature": "Fc (IgG1 core)",
                        "anchor_start": int(fc.start),
                        "anchor_end": int(fc.end),
                        "motif": motif,
                        "motif_start": motif_start,
                        "motif_end": motif_end,
                    },
                }
            )
    # Anchored Fc-engineering motif calls.
    # Guardrail: only evaluate within Fc-neighborhood window after Fc anchoring.
    # This avoids naive whole-sequence motif scanning.
    win_lo = max(0, int(fc.start) - 120)
    win_hi = min(len(s), int(fc.end) + 120)
    neighborhood = s[win_lo:win_hi]

    lalapg_hits: list[tuple[int, int]] = []
    start = 0
    while True:
        j = neighborhood.find("LALAPG", start)
        if j < 0:
            break
        a = int(win_lo + j)
        b = int(a + 6)
        lalapg_hits.append((a, b))
        start = j + 1

    for a, b in lalapg_hits:
        out["features"].append(
            {
                "name": "LALAPG",
                "group": "Engineering features",
                "kind": "motif",
                "feature_type": "motif",
                "start": int(a),
                "end": int(b),
                "confidence": float(max(0.0, min(1.0, min(float(fc.confidence), 0.95)))),
                "source": "computed",
                "status": "success",
                "method": "fc_anchor_window_exact",
                "tool_name": "psi_constant_regions",
                "tool_version": "d138",
                "meta": {
                    "anchor_feature": "Fc (IgG1 core)",
                    "anchor_start": int(fc.start),
                    "anchor_end": int(fc.end),
                    "window_start": int(win_lo),
                    "window_end": int(win_hi),
                },
            }
        )

    # Emit LALA only when not subsumed by a LALAPG hit.
    start = 0
    while True:
        j = neighborhood.find("LALA", start)
        if j < 0:
            break
        a = int(win_lo + j)
        b = int(a + 4)
        overlap = any(a < x1 and b > x0 for (x0, x1) in lalapg_hits)
        if not overlap:
            out["features"].append(
                {
                    "name": "LALA",
                    "group": "Engineering features",
                    "kind": "motif",
                    "feature_type": "motif",
                    "start": int(a),
                    "end": int(b),
                    "confidence": float(max(0.0, min(1.0, min(float(fc.confidence), 0.95)))),
                    "source": "computed",
                    "status": "success",
                    "method": "fc_anchor_window_exact",
                    "tool_name": "psi_constant_regions",
                    "tool_version": "d138",
                    "meta": {
                        "anchor_feature": "Fc (IgG1 core)",
                        "anchor_start": int(fc.start),
                        "anchor_end": int(fc.end),
                        "window_start": int(win_lo),
                        "window_end": int(win_hi),
                    },
                }
            )
        start = j + 1

    return out
