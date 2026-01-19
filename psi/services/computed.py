from __future__ import annotations

import os
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.biochem import (
    aa_composition,
    basic_developability_proxies,
    cysteine_count,
    extinction_coefficient_a280,
    instability_index,
    molecular_weight_da,
    motif_heuristics,
    sequence_length,
    theoretical_pI,
)
from psi.core.fasta import parse_fasta, sha256_text, to_fasta, normalize_aa_sequence
from psi.core.models import Molecule, MoleculeComponent, PropertyRun, PropertyRunEvent, PropertyValue
from psi.core.utils import json_dumps_compact, now_utc, model_to_dict
from psi.core.computed_registry import list_calculators
from psi.services.domains import ensure_sequence_entity, ensure_liability_sites_artifact


FAST_TIER = "FAST"
HEAVY_TIER = "HEAVY"


ROLE_ORDER = [
    "HC1",
    "LC1",
    "HC2",
    "LC2",
    "VH",
    "VL",
    "linker",
    "fusion",
]


def _input_hash_from_components(components: List[MoleculeComponent]) -> str:
    parts = []
    for c in sorted(components, key=lambda x: (ROLE_ORDER.index(x.role) if x.role in ROLE_ORDER else 999, x.role)):
        parts.append(f"{c.role}:{c.sha256}")
    return sha256("|".join(parts).encode("utf-8")).hexdigest()


def _ensure_legacy_fusion_component(db: Session, m: Molecule) -> List[MoleculeComponent]:
    comps = db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()
    if comps:
        return comps
    # Deterministic migration for legacy records: store entire blob as a single fusion component.
    blob = (m.sequences or "").strip()
    if not blob:
        return []
    c = MoleculeComponent(
        molecule_id=m.id,
        role="fusion",
        fasta=blob,
        sha256=sha256_text(blob),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(c)
    db.commit()
    return [c]


def _assembled_sequence_for_fast_props(m: Molecule, comps: Dict[str, str]) -> Tuple[str, Dict[str, Any]]:
    """Return (assembled_sequence, meta) for FAST properties.

    For IgG: concatenate chains (HC1+LC1+HC2+LC2) using inference rules.
    For scFv: VH + detected/linker + VL.
    For legacy: attempt to extract AA from sequences blob.
    """
    fmt = (m.molecule_format or "").strip()
    meta: Dict[str, Any] = {}

    if fmt == "IgG":
        hc1 = comps.get("HC1", "")
        lc1 = comps.get("LC1", "")
        hc2 = comps.get("HC2") or hc1
        lc2 = comps.get("LC2") or lc1
        meta.update({"inferred_same_heavy": "HC2" not in comps, "inferred_common_light": "LC2" not in comps})
        assembled = "".join([hc1, lc1, hc2, lc2])
        return assembled, meta

    if fmt == "scFv":
        vh = comps.get("VH", "")
        vl = comps.get("VL", "")
        linker = comps.get("linker", "")
        if not linker:
            # Detect common GS linkers if user pasted a single combined sequence in VH or VL fields.
            # Otherwise leave empty.
            linker = ""
        assembled = "".join([vh, linker, vl])
        return assembled, meta

    # legacy/unstructured: best-effort extract AA letters from sequences blob
    blob = m.sequences or ""
    # If FASTA, concatenate records; else normalize.
    recs = parse_fasta(blob)
    if recs:
        assembled = "".join(r.sequence for r in recs)
    else:
        assembled = normalize_aa_sequence(blob)
    return assembled, meta


def _auto_description(m: Molecule, comps: Dict[str, str]) -> str:
    fmt = (m.molecule_format or "").strip() or "Legacy"
    if fmt == "IgG":
        parts = ["IgG"]
        hc1 = "present" if comps.get("HC1") else "missing"
        lc1 = "present" if comps.get("LC1") else "missing"
        parts.append(f"HC1={hc1}, LC1={lc1}")
        same_hc = "HC2" not in comps
        common_lc = "LC2" not in comps
        if same_hc:
            parts.append("HC2 inferred = HC1 (same heavy on both arms)")
        else:
            parts.append("HC2 provided (two-heavy / bispecific supported)")
        if common_lc:
            parts.append("LC2 inferred = LC1 (common light chain)")
        else:
            parts.append("LC2 provided")
        # simple fusion detection
        if "fusion" in comps:
            parts.append("fusion: present")
        return "; ".join(parts)
    if fmt == "scFv":
        parts = ["scFv", "VH+VL"]
        if "linker" in comps and comps.get("linker"):
            parts.append("linker: provided")
        else:
            parts.append("linker: auto-detect (GS motifs) during annotation")
        if "fusion" in comps:
            parts.append("fusion: present")
        return "; ".join(parts)
    return "Legacy/unstructured molecule record (sequences stored as raw text)."


def _store_value(db: Session, *, run: PropertyRun, key: str, label: str, value: Any, tier: str) -> None:
    pv = PropertyValue(
        run_id=run.id,
        molecule_id=run.molecule_id,
        property_key=key,
        label=label,
        value_json=json_dumps_compact(value),
        tier=tier,
        created_at=now_utc(),
    )
    db.add(pv)


def _log_event(db: Session, *, run: PropertyRun, step: str, level: str, message: str, payload: Any | None = None) -> None:
    ev = PropertyRunEvent(
        run_id=run.id,
        molecule_id=run.molecule_id,
        timestamp=now_utc(),
        step=step,
        level=level,
        message=message,
        payload_json=json_dumps_compact(payload) if payload is not None else None,
    )
    db.add(ev)


def run_computed_properties(
    db: Session,
    *,
    molecule_id: int,
    trigger_reason: str,
    compute_tier: str = "FAST",
) -> PropertyRun:
    """Compute FAST properties (always) and optionally HEAVY (gated).

    This function is safe to call repeatedly. It creates a new PropertyRun and new PropertyValues.
    """
    m = db.get(Molecule, molecule_id)
    if not m:
        raise KeyError("Molecule not found")

    # Ensure legacy fusion component exists (deterministic), but do not do VH/VL extraction for legacy.
    comps_list = _ensure_legacy_fusion_component(db, m)
    comps_list = db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()
    input_hash = _input_hash_from_components(comps_list)

    run = PropertyRun(
        molecule_id=m.id,
        input_hash=input_hash,
        trigger_reason=trigger_reason,
        compute_tier=compute_tier,
        status="running",
        error=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    _log_event(db, run=run, step="start", level="info", message="Computed run started", payload={"input_hash": input_hash, "tier": compute_tier, "trigger_reason": trigger_reason})
    record_audit(db, entity_type="Molecule", entity_id=m.id, action="computed_run", before=None, after={"property_run_id": run.id, "input_hash": input_hash, "tier": compute_tier, "trigger_reason": trigger_reason})
    db.commit()

    try:
        comps: Dict[str, str] = {c.role: c.fasta for c in comps_list}
        _log_event(db, run=run, step="inputs", level="info", message="Loaded molecule components", payload={"roles": list(comps.keys())})

        # Update auto description (deterministic) without overwriting user/legacy description.
        before_m = model_to_dict(m)
        m.description_auto = _auto_description(m, comps)
        # Mirror user description into legacy description for compatibility.
        if m.description_user:
            m.description = m.description_user
        m.updated_at = now_utc()
        db.add(m)
        db.commit()
        record_audit(db, entity_type="Molecule", entity_id=m.id, action="update", before=before_m, after=model_to_dict(m), reason="auto description refresh")
        db.commit()

        assembled, meta = _assembled_sequence_for_fast_props(m, {k: normalize_aa_sequence(v) for k, v in comps.items()})
        _log_event(db, run=run, step="assemble", level="info", message="Assembled sequence for FAST properties", payload={"assembled_length": len(assembled), **meta})
        fmt = (m.molecule_format or "").strip() or "legacy"
	# Auto-generated deterministic description
        desc_parts = []
        desc_parts.append(f"format={fmt}")
        if fmt == "IgG":
            same_hc = "HC2" not in comps or (comps.get("HC2") == comps.get("HC1"))
            common_lc = "LC2" not in comps or (comps.get("LC2") == comps.get("LC1"))
            desc_parts.append("composition=HC1+LC1" + ("+HC2" if "HC2" in comps else "") + ("+LC2" if "LC2" in comps else ""))
            if same_hc:
                desc_parts.append("inferred=same_HC_on_both_arms")
            if common_lc:
                desc_parts.append("inferred=common_light_chain")
        elif fmt == "scFv":
            linker = "linker" if "linker" in comps else "(auto-detect_GS_linker)"
            desc_parts.append(f"composition=VH-{linker}-VL")
        if "fusion" in comps:
            desc_parts.append("fusion=present")
        m.description_auto = "; ".join(desc_parts)
        db.add(m)
        record_audit(db, entity_type="Molecule", entity_id=m.id, action="computed_description", before=None, after={"description_auto": m.description_auto})
        db.commit()

        # FAST properties
        _log_event(db, run=run, step="fast_props", level="info", message="Computing FAST properties")
        _store_value(db, run=run, key="fast.sequence_length", label="Sequence length", value=sequence_length(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.molecular_weight_da", label="Molecular weight (Da)", value=molecular_weight_da(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.theoretical_pI", label="Theoretical pI", value=theoretical_pI(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.extinction_coefficient_a280", label="Extinction coefficient (A280)", value=extinction_coefficient_a280(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.amino_acid_composition", label="Amino acid composition", value=aa_composition(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.cysteine_count", label="Cysteine count", value=cysteine_count(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.motif_heuristics", label="Motif heuristics", value=motif_heuristics(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.instability_index", label="Instability index", value=instability_index(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.developability_proxies", label="Basic developability proxies", value=basic_developability_proxies(assembled), tier=FAST_TIER)
        _store_value(db, run=run, key="fast.assembly_inference", label="Assembly inference", value=meta, tier=FAST_TIER)

        # vNext: positional liability sites cached per component (cheap, reusable)
        try:
            _log_event(db, run=run, step="liability_sites", level="info", message="Computing liability sites artifacts for components")
            for c in comps_list:
                seq_norm = normalize_aa_sequence(c.fasta)
                if not seq_norm:
                    continue
                se = ensure_sequence_entity(db, seq_norm)
                # ensure component points to sequence entity (additive)
                if not c.sequence_entity_id:
                    c.sequence_entity_id = se.id
                    db.add(c)
                ensure_liability_sites_artifact(db, sequence_id=se.id, tool_name="psi", tool_version="vNext", settings_hash="default")
            db.commit()
        except Exception as e:
            _log_event(db, run=run, step="liability_sites", level="warn", message="Liability sites artifact generation failed", payload={"error": str(e)})

        # vNext: Antibody numbering is manual-only and cached at the domain level.
        # Keep a lightweight architecture classification for structured molecules.
        fmt = (m.molecule_format or "").strip()
        if fmt in ("IgG", "scFv"):
            arch = fmt
            if "fusion" in comps and comps.get("fusion"):
                arch = f"{fmt} + fusion"
            _store_value(db, run=run, key="fast.sequence_annotation", label="Sequence annotation", value={"architecture": arch, "format": fmt}, tier=FAST_TIER)
            _log_event(db, run=run, step="numbering", level="info", message="Skipping antibody numbering (manual-only in vNext)")

        # Heavy compute (extension-based) – optional.
        heavy_global = os.getenv("PSI_ENABLE_HEAVY_COMPUTE", "").strip() == "1"
        if compute_tier == "FAST+HEAVY" and heavy_global and int(m.heavy_compute_enabled or 0) == 1:
            ctx = {
                "molecule_id": m.id,
                "molecule_format": m.molecule_format,
                "components": {k: normalize_aa_sequence(v) for k, v in comps.items()},
                "assembled_sequence": assembled,
            }
            heavy_calcs = list_calculators(tier=HEAVY_TIER)
            for c in heavy_calcs:
                try:
                    out = c.fn(ctx)
                    _store_value(db, run=run, key=c.key, label=c.label, value=out, tier=HEAVY_TIER)
                except Exception as e:
                    _store_value(db, run=run, key=c.key, label=c.label, value={"error": str(e)}, tier=HEAVY_TIER)

        run.status = "success"
        run.updated_at = now_utc()
        db.add(run)
        _log_event(db, run=run, step="end", level="info", message="Computed run completed")
        db.commit()
        return run
    except Exception as e:
        run.status = "failure"
        run.error = str(e)
        run.updated_at = now_utc()
        db.add(run)
        _log_event(db, run=run, step="end", level="error", message="Computed run failed", payload={"error": str(e)})
        db.commit()
        record_audit(db, entity_type="Molecule", entity_id=m.id, action="computed_run_failed", before=None, after={"property_run_id": run.id, "error": str(e)})
        db.commit()
        return run


def get_property_runs(db: Session, molecule_id: int) -> List[PropertyRun]:
    return (
        db.query(PropertyRun)
        .filter(PropertyRun.molecule_id == molecule_id)
        .order_by(PropertyRun.created_at.desc())
        .all()
    )


def get_run_values(db: Session, run_id: int) -> List[PropertyValue]:
    return db.query(PropertyValue).filter(PropertyValue.run_id == run_id).order_by(PropertyValue.id.asc()).all()
