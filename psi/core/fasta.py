from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable, List, Optional, Tuple


FASTA_HEADER_RE = re.compile(r"^>\s*(?P<header>.+?)\s*$")


@dataclass(frozen=True)
class FastaRecord:
    header: str
    sequence: str

    @property
    def sha256(self) -> str:
        return sha256(self.sequence.encode("utf-8")).hexdigest()


def normalize_aa_sequence(seq: str) -> str:
    """Normalize an amino-acid sequence.

    - strips whitespace
    - removes digits
    - uppercases
    - keeps only letters and common ambiguity codes (X)
    """
    if not seq:
        return ""
    seq = re.sub(r"\s+", "", seq)
    seq = re.sub(r"\d+", "", seq)
    seq = seq.upper()
    # keep letters only
    seq = re.sub(r"[^A-Z]", "", seq)
    return seq


def parse_fasta(text: str) -> List[FastaRecord]:
    """Parse a FASTA string into records.

    Best-effort: if no headers, returns empty list.
    """
    if not text:
        return []
    lines = text.splitlines()
    records: List[FastaRecord] = []
    cur_header: Optional[str] = None
    cur_seq: List[str] = []
    for line in lines:
        m = FASTA_HEADER_RE.match(line.strip())
        if m:
            if cur_header is not None:
                records.append(FastaRecord(cur_header, normalize_aa_sequence("".join(cur_seq))))
            cur_header = m.group("header").strip()
            cur_seq = []
        else:
            if cur_header is None:
                continue
            cur_seq.append(line.strip())
    if cur_header is not None:
        records.append(FastaRecord(cur_header, normalize_aa_sequence("".join(cur_seq))))
    return records


def to_fasta(records: Iterable[Tuple[str, str]]) -> str:
    out: List[str] = []
    for header, seq in records:
        seq_n = normalize_aa_sequence(seq)
        out.append(f">{header}")
        # wrap at 60
        for i in range(0, len(seq_n), 60):
            out.append(seq_n[i : i + 60])
    return "\n".join(out).strip() + ("\n" if out else "")


def sha256_text(text: str) -> str:
    return sha256((text or "").encode("utf-8")).hexdigest()
