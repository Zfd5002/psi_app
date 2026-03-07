from __future__ import annotations

import re
from typing import Any


_MUT_RE = re.compile(r"^([A-Za-z])(\d+)([A-Za-z])$")


def parse_mutation_notation(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    raw = str(text or "").strip()
    if not raw:
        return [], []
    tokens = [t.strip() for t in re.split(r"[\s,;]+", raw) if t.strip()]
    out: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_pos: set[int] = set()
    for tok in tokens:
        m = _MUT_RE.match(tok)
        if not m:
            errors.append(f"Invalid token: {tok}")
            continue
        wt = str(m.group(1)).upper()
        pos = int(m.group(2))
        to = str(m.group(3)).upper()
        if pos <= 0:
            errors.append(f"Invalid position in token: {tok}")
            continue
        if pos in seen_pos:
            errors.append(f"Duplicate position in direct notation: {pos}")
            continue
        seen_pos.add(pos)
        out.append({"from": wt, "position": pos, "to": to, "token": tok})
    return out, errors


def normalize_mutation_queue(
    *,
    component_role: str,
    parent_sequence: str,
    clicked_mutations: list[dict[str, Any]],
    direct_notation_text: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    q: dict[int, dict[str, Any]] = {}
    seq = str(parent_sequence or "").strip().upper()
    role = str(component_role or "")

    def _put(entry: dict[str, Any]) -> None:
        pos = int(entry.get("position") or 0)
        if pos <= 0:
            return
        q[pos] = {
            "component_role": role,
            "position": pos,
            "from": str(entry.get("from") or "").upper(),
            "to": str(entry.get("to") or "").upper(),
        }

    for c in clicked_mutations or []:
        if not isinstance(c, dict):
            continue
        _put(c)

    parsed, parse_errors = parse_mutation_notation(direct_notation_text)
    errors.extend(parse_errors)
    for p in parsed:
        _put(p)

    out: list[dict[str, Any]] = []
    for pos in sorted(q.keys()):
        row = q[pos]
        if pos > len(seq):
            errors.append(f"Mutation out of range: {row['from']}{pos}{row['to']}")
            continue
        actual = seq[pos - 1]
        if row["from"] and actual != row["from"]:
            errors.append(f"WT mismatch at {pos}: expected {row['from']}, found {actual}")
            continue
        out.append(row)
    return out, errors


def build_sequence_preview(
    *,
    parent_sequence: str,
    mutations: list[dict[str, Any]],
) -> dict[str, Any]:
    seq = list(str(parent_sequence or "").strip().upper())
    errors: list[str] = []
    applied: list[dict[str, Any]] = []
    for m in sorted(
        [x for x in (mutations or []) if isinstance(x, dict)],
        key=lambda x: int(x.get("position") or 0),
    ):
        pos = int(m.get("position") or 0)
        frm = str(m.get("from") or "").upper()
        to = str(m.get("to") or "").upper()
        if pos <= 0 or pos > len(seq):
            errors.append(f"Out of range: {frm}{pos}{to}")
            continue
        actual = seq[pos - 1]
        if frm and actual != frm:
            errors.append(f"WT mismatch at {pos}: expected {frm}, found {actual}")
            continue
        seq[pos - 1] = to
        applied.append({"position": pos, "from": actual, "to": to})
    edited = "".join(seq)
    return {
        "original_sequence": str(parent_sequence or "").strip().upper(),
        "edited_sequence": edited,
        "changed_positions": [int(a["position"]) for a in applied],
        "changes": applied,
        "errors": errors,
    }
