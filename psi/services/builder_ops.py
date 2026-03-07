from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping


def clone_components(*, parent_components: Mapping[str, str]) -> dict[str, str]:
    """Return a deterministic copy of parent component sequences."""
    out: dict[str, str] = {}
    for role in sorted(str(k) for k in parent_components.keys()):
        seq = str(parent_components.get(role) or "").strip()
        if seq:
            out[role] = seq
    return out


@dataclass(frozen=True)
class PointMutation:
    wt: str
    position: int  # 1-based
    mut: str
    token: str


_MUTATION_RE = re.compile(r"^([A-Za-z])(\d+)([A-Za-z])$")


def parse_point_mutation_tokens(text: str) -> tuple[list[PointMutation], list[str]]:
    raw = str(text or "").strip()
    if not raw:
        return [], ["At least one mutation token is required."]
    pieces = [p.strip() for p in re.split(r"[,\s;]+", raw) if p.strip()]
    mutations: list[PointMutation] = []
    errors: list[str] = []
    seen_positions: set[int] = set()
    for token in pieces:
        m = _MUTATION_RE.match(token)
        if not m:
            errors.append(f"Invalid mutation token: {token}")
            continue
        wt = str(m.group(1)).upper()
        pos = int(m.group(2))
        mut = str(m.group(3)).upper()
        if pos <= 0:
            errors.append(f"Mutation position must be >= 1: {token}")
            continue
        if pos in seen_positions:
            errors.append(f"Duplicate mutation position: {pos}")
            continue
        seen_positions.add(pos)
        mutations.append(PointMutation(wt=wt, position=pos, mut=mut, token=token))
    return mutations, errors


def apply_point_mutations(*, sequence: str, mutations: list[PointMutation]) -> tuple[str, list[str]]:
    seq = str(sequence or "").strip().upper()
    if not seq:
        return "", ["Target sequence is empty."]
    if not mutations:
        return seq, []
    seq_chars = list(seq)
    errors: list[str] = []
    for mut in mutations:
        idx = int(mut.position) - 1
        if idx < 0 or idx >= len(seq_chars):
            errors.append(f"Mutation out of range: {mut.token}")
            continue
        actual = str(seq_chars[idx]).upper()
        if actual != str(mut.wt).upper():
            errors.append(
                f"WT mismatch at position {mut.position}: expected {mut.wt}, found {actual}"
            )
            continue
        seq_chars[idx] = str(mut.mut).upper()
    return "".join(seq_chars), errors
