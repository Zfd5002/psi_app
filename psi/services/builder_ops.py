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
_FC_TAIL_LEN = 10
FC_PRESETS: dict[str, str] = {
    "human_igg1": "ASTKGPSVFP",
    "mouse_igg2a": "AKTTAPSVYF",
    "fab_no_fc": "",
}

FRAMEWORK_PRESETS: dict[str, dict[str, str]] = {
    "human_vh3_vk1": {
        "vh_prefix": "EVQLVESGGG",
        "vh_mid1": "WVRQAPGKGLEW",
        "vh_mid2": "RFTISRDNSKNTLYLQMNSLRAEDTAVYYC",
        "vh_suffix": "WGQGTLVTVSS",
        "vl_prefix_kappa": "DIQMTQSPSS",
        "vl_prefix_lambda": "QSVLTQPPSA",
        "vl_mid1": "LSASVGDRVTITC",
        "vl_mid2": "WYQQKPGQAPRLLIY",
        "vl_suffix": "GVPDRFSGSGSGTDFTLTISSLQPEDFATYYCQQ",
        "vl_tail": "FGGGTKLEIK",
    },
    "human_vh1_vk1": {
        "vh_prefix": "QVQLVQSGAE",
        "vh_mid1": "VKKPGASVKVS",
        "vh_mid2": "YGSTYYADSVKGRFTISRDNSKNTLYLQMNSLRAEDTAVYYC",
        "vh_suffix": "WGQGTLVTVSS",
        "vl_prefix_kappa": "DIQMTQSPSS",
        "vl_prefix_lambda": "QSVLTQPPSA",
        "vl_mid1": "LSASVGDRVTITC",
        "vl_mid2": "WYQQKPGQAPRLLIY",
        "vl_suffix": "GVPDRFSGSGSGTDFTLTISSLQPEDFATYYCQQ",
        "vl_tail": "FGGGTKLEIK",
    },
}


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


def apply_fc_swap(*, components: Mapping[str, str], preset: str) -> tuple[dict[str, str], list[str]]:
    key = str(preset or "").strip().lower()
    if key not in FC_PRESETS:
        return dict(components), [f"Unsupported Fc preset: {preset}"]
    out = {str(k): str(v or "") for k, v in components.items()}
    if "HC1" not in out:
        return out, ["Heavy chain HC1 is required for Fc swap."]
    tail = FC_PRESETS[key]

    def _swap(seq: str) -> str:
        s = str(seq or "").strip().upper()
        if not s:
            return s
        if key == "fab_no_fc":
            return s[:-_FC_TAIL_LEN] if len(s) > _FC_TAIL_LEN else s
        if len(s) > _FC_TAIL_LEN:
            return s[:-_FC_TAIL_LEN] + tail
        return s + tail

    out["HC1"] = _swap(out.get("HC1", ""))
    if "HC2" in out:
        out["HC2"] = _swap(out.get("HC2", ""))
    return out, []


def apply_kih_knob(*, sequence: str) -> tuple[str, list[str]]:
    s = str(sequence or "").strip().upper()
    if not s:
        return s, ["Target sequence is empty."]
    if len(s) < 6:
        return s, ["Sequence too short for KIH knob."]
    chars = list(s)
    chars[4] = "W"
    return "".join(chars), []


def apply_kih_hole(*, sequence: str) -> tuple[str, list[str]]:
    s = str(sequence or "").strip().upper()
    if not s:
        return s, ["Target sequence is empty."]
    if len(s) < 6:
        return s, ["Sequence too short for KIH hole."]
    chars = list(s)
    chars[4] = "T"
    return "".join(chars), []


def remove_kih(*, sequence: str, fallback_residue: str = "A") -> tuple[str, list[str]]:
    s = str(sequence or "").strip().upper()
    if not s:
        return s, ["Target sequence is empty."]
    if len(s) < 6:
        return s, ["Sequence too short for KIH remove."]
    chars = list(s)
    chars[4] = str(fallback_residue or "A").upper()[0]
    return "".join(chars), []


def apply_cdr_graft(
    *,
    framework_preset: str,
    light_chain_type: str,
    numbering_scheme: str,
    cdrs: Mapping[str, str],
) -> tuple[dict[str, str], list[str]]:
    fp = str(framework_preset or "").strip().lower()
    lct = str(light_chain_type or "").strip().lower()
    ns = str(numbering_scheme or "").strip().lower()
    if fp not in FRAMEWORK_PRESETS:
        return {}, [f"Unsupported framework preset: {framework_preset}"]
    if lct not in {"kappa", "lambda"}:
        return {}, [f"Unsupported light chain type: {light_chain_type}"]
    if ns not in {"kabat", "chothia", "imgt"}:
        return {}, [f"Unsupported numbering scheme: {numbering_scheme}"]
    f = FRAMEWORK_PRESETS[fp]
    req = ["HCDR1", "HCDR2", "HCDR3", "LCDR1", "LCDR2", "LCDR3"]
    missing = [k for k in req if not str(cdrs.get(k) or "").strip()]
    if missing:
        return {}, [f"Missing CDR fields: {', '.join(missing)}"]
    vh = (
        f["vh_prefix"]
        + str(cdrs["HCDR1"]).strip().upper()
        + f["vh_mid1"]
        + str(cdrs["HCDR2"]).strip().upper()
        + f["vh_mid2"]
        + str(cdrs["HCDR3"]).strip().upper()
        + f["vh_suffix"]
    )
    vl_prefix = f["vl_prefix_kappa"] if lct == "kappa" else f["vl_prefix_lambda"]
    vl = (
        vl_prefix
        + str(cdrs["LCDR1"]).strip().upper()
        + f["vl_mid1"]
        + str(cdrs["LCDR2"]).strip().upper()
        + f["vl_mid2"]
        + str(cdrs["LCDR3"]).strip().upper()
        + f["vl_suffix"]
        + f["vl_tail"]
    )
    return {
        "HC1": vh,
        "HC2": vh,
        "LC1": vl,
        "LC2": vl,
    }, []


def build_mutation_panel_members(
    *,
    mutation_tokens_text: str,
    include_pair_combinations: bool,
    explicit_combos_text: str,
) -> list[dict[str, object]]:
    raw_tokens = [t.strip().upper() for t in re.split(r"[,\s;]+", str(mutation_tokens_text or "").strip()) if t.strip()]
    tokens: list[str] = []
    seen: set[str] = set()
    for tok in raw_tokens:
        if tok in seen:
            continue
        seen.add(tok)
        tokens.append(tok)

    combos: list[tuple[str, ...]] = [(tok,) for tok in tokens]
    if bool(include_pair_combinations):
        for i in range(len(tokens)):
            for j in range(i + 1, len(tokens)):
                combos.append((tokens[i], tokens[j]))

    explicit_groups = [g.strip() for g in re.split(r"[;|]+", str(explicit_combos_text or "").strip()) if g.strip()]
    for group in explicit_groups:
        parts = [p.strip().upper() for p in re.split(r"[+,\\s]+", group) if p.strip()]
        if not parts:
            continue
        unique_parts: list[str] = []
        seen_parts: set[str] = set()
        for p in parts:
            if p in seen_parts:
                continue
            seen_parts.add(p)
            unique_parts.append(p)
        if unique_parts:
            combos.append(tuple(unique_parts))

    deduped: list[tuple[str, ...]] = []
    seen_combo: set[tuple[str, ...]] = set()
    for combo in combos:
        if combo in seen_combo:
            continue
        seen_combo.add(combo)
        deduped.append(combo)

    members: list[dict[str, object]] = []
    for idx, combo in enumerate(deduped, start=1):
        label = "+".join(combo)
        members.append(
            {
                "sort_index": idx,
                "member_label": label,
                "mode": "point_mutation",
                "operations": [{"type": "point_mutation", "component": "HC1", "mutations": " ".join(combo)}],
            }
        )
    return members


def build_fc_panel_members(*, presets_text: str) -> list[dict[str, object]]:
    raw = [p.strip().lower() for p in re.split(r"[,\s;]+", str(presets_text or "").strip()) if p.strip()]
    allowed = ["human_igg1", "mouse_igg2a", "fab_no_fc"]
    selected: list[str] = []
    seen: set[str] = set()
    for p in raw:
        if p not in allowed or p in seen:
            continue
        seen.add(p)
        selected.append(p)
    if not selected:
        selected = list(allowed)
    members: list[dict[str, object]] = []
    for idx, preset in enumerate(selected, start=1):
        members.append(
            {
                "sort_index": idx,
                "member_label": preset,
                "mode": "fc_swap",
                "operations": [{"type": "fc_swap", "preset": preset}],
            }
        )
    return members


def build_kih_panel_members(*, kih_presets_text: str) -> list[dict[str, object]]:
    raw = [p.strip().lower() for p in re.split(r"[,\s;]+", str(kih_presets_text or "").strip()) if p.strip()]
    allowed = ["off", "on_knob", "on_hole"]
    selected: list[str] = []
    seen: set[str] = set()
    for p in raw:
        if p not in allowed or p in seen:
            continue
        seen.add(p)
        selected.append(p)
    if not selected:
        selected = ["off", "on_knob"]

    action_map = {"off": "remove", "on_knob": "apply_knob", "on_hole": "apply_hole"}
    members: list[dict[str, object]] = []
    for idx, preset in enumerate(selected, start=1):
        members.append(
            {
                "sort_index": idx,
                "member_label": preset,
                "mode": "kih_toggle",
                "operations": [{"type": "kih_toggle", "action": action_map[preset]}],
            }
        )
    return members


def build_scaffold_panel_members(
    *,
    scaffold_presets_text: str,
    light_chain_type: str,
    numbering_scheme: str,
    cdrs: Mapping[str, str],
) -> list[dict[str, object]]:
    raw = [p.strip().lower() for p in re.split(r"[,\s;]+", str(scaffold_presets_text or "").strip()) if p.strip()]
    allowed = sorted(FRAMEWORK_PRESETS.keys())
    selected: list[str] = []
    seen: set[str] = set()
    for p in raw:
        if p not in allowed or p in seen:
            continue
        seen.add(p)
        selected.append(p)
    if not selected:
        selected = ["human_vh3_vk1", "human_vh1_vk1"]
    members: list[dict[str, object]] = []
    for idx, preset in enumerate(selected, start=1):
        members.append(
            {
                "sort_index": idx,
                "member_label": preset,
                "mode": "cdr_graft",
                "member_summary": f"scaffold={preset} reconstructed_from_cdrs",
                "operations": [
                    {
                        "type": "cdr_graft",
                        "framework_preset": preset,
                        "light_chain_type": str(light_chain_type or "kappa").strip().lower() or "kappa",
                        "numbering_scheme": str(numbering_scheme or "kabat").strip().lower() or "kabat",
                        "HCDR1": str(cdrs.get("HCDR1") or "").strip(),
                        "HCDR2": str(cdrs.get("HCDR2") or "").strip(),
                        "HCDR3": str(cdrs.get("HCDR3") or "").strip(),
                        "LCDR1": str(cdrs.get("LCDR1") or "").strip(),
                        "LCDR2": str(cdrs.get("LCDR2") or "").strip(),
                        "LCDR3": str(cdrs.get("LCDR3") or "").strip(),
                    }
                ],
            }
        )
    return members
