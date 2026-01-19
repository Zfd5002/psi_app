"""
ANARCI-based antibody domain detection helpers.

ANARCI => domain detection (VH/VL span in a longer chain)
abnumber => numbering/CDRs once the variable domain subsequence is extracted
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class AntibodyDomainError(RuntimeError):
    pass


@dataclass(frozen=True)
class VariableDomainSpan:
    start: int          # 0-based start index in the input sequence (inclusive)
    end_excl: int       # 0-based end index in the input sequence (exclusive)
    chain_type: Optional[str] = None  # 'H' / 'K' / 'L' if available


def _call_anarci_single(seq: str, scheme: str):
    """Call ANARCI in a way that works across minor API differences."""
    try:
        from anarci import anarci as anarci_fn
    except Exception as e:
        raise AntibodyDomainError(f"Failed to import ANARCI: {e}") from e

    last_err = None
    for payload in ([( "query", seq )], [seq]):
        try:
            return anarci_fn(payload, scheme=scheme)
        except TypeError as e:
            last_err = e
            continue
        except Exception as e:
            raise AntibodyDomainError(f"ANARCI call failed: {e}") from e

    raise AntibodyDomainError(f"ANARCI call signature mismatch: {last_err}")


def extract_variable_span_anarci(seq: str, scheme: str = "imgt") -> VariableDomainSpan:
    """
    Return the first ANARCI-detected variable-domain span in `seq`.
    Normalizes ANARCI's (often inclusive) end index to Python end-exclusive.
    """
    if not isinstance(seq, str) or not seq:
        raise AntibodyDomainError("Sequence must be a non-empty string")

    out = _call_anarci_single(seq, scheme=scheme)

    if not isinstance(out, tuple) or len(out) < 1:
        raise AntibodyDomainError(f"Unexpected ANARCI return type: {type(out)}")

    results = out[0]
    if results is None:
        raise AntibodyDomainError("ANARCI returned no results")

    try:
        seq_hits = results[0]
    except Exception as e:
        raise AntibodyDomainError(f"Unexpected ANARCI results structure: {e}") from e

    if not seq_hits:
        raise AntibodyDomainError("ANARCI found no antibody variable domain")

    first_hit = seq_hits[0]
    if not isinstance(first_hit, (list, tuple)) or len(first_hit) < 3:
        raise AntibodyDomainError(f"Unexpected ANARCI hit format: {first_hit!r}")

    start = first_hit[1]
    end = first_hit[2]

    if not isinstance(start, int) or not isinstance(end, int):
        raise AntibodyDomainError(f"Invalid start/end from ANARCI: {start!r}, {end!r}")

    end_excl = end + 1

    if start < 0 or end_excl <= start or end_excl > len(seq):
        raise AntibodyDomainError(
            f"Invalid span from ANARCI: start={start}, end_excl={end_excl}, len={len(seq)}"
        )

    return VariableDomainSpan(start=start, end_excl=end_excl, chain_type=None)
