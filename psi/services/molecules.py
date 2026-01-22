from __future__ import annotations

from sqlalchemy.orm import Session

from psi.core.audit import record_audit
from psi.core.models import (
    AuditEvent,
    Batch,
    DataRecord,
    Evidence,
    File as StoredFile,
    FileLink,
    Molecule,
    Program,
    MoleculeComponent,
    DomainInstance,
    DomainArtifact,
    PropertyRunEvent,
    PropertyRun,
    PropertyValue,
)
from psi.core.utils import model_to_dict, now_utc
import json
from psi.core.fasta import normalize_aa_sequence, sha256_text, to_fasta
from psi.core.db import SessionLocal
from psi.services.computed import run_computed_properties, get_property_runs, get_run_values
from psi.services.domains import extract_domains_for_molecule
from psi.services.numbering import get_numbering_artifacts_for_molecule
from psi.core.reference_features import detect_pdl1_features
from psi.core.deps import heavy_compute_available_for_molecule
from psi.core.biochem import liability_sites
from psi.core.annotations import detect_linker_spans, detect_fc_region, dedupe_features


def _confidence_from_mismatches(mismatches: int, length: int) -> float:
    if length <= 0:
        return 0.0
    mm = max(0, int(mismatches))
    return max(0.0, min(1.0, 1.0 - (mm / float(length))))


def _pack_segments(segments: list[dict]) -> list[list[dict]]:
    """Greedy non-overlap packing.

    Input: list of dicts with start_idx/end_idx.
    Output: list of rows (each row is list of segments).
    """
    segs = sorted(segments, key=lambda s: (int(s["start_idx"]), -(int(s["end_idx"]) - int(s["start_idx"]))))
    rows: list[list[dict]] = []
    for seg in segs:
        placed = False
        s0 = int(seg["start_idx"])
        e0 = int(seg["end_idx"])
        for row in rows:
            # check overlap against last segment in row (row is in order)
            last = row[-1]
            if int(last["end_idx"]) <= s0:
                row.append(seg)
                placed = True
                break
        if not placed:
            rows.append([seg])
    return rows


def list_molecules(db: Session) -> tuple[list[Molecule], list[Program]]:
    molecules = db.query(Molecule).order_by(Molecule.created_at.desc()).all()
    programs = db.query(Program).order_by(Program.name.asc()).all()
    return molecules, programs


def get_molecule(db: Session, molecule_id: int) -> Molecule | None:
    return db.get(Molecule, molecule_id)


def get_molecule_detail(db: Session, molecule_id: int, *, pdl1_allowed_mismatches: int = 0) -> dict:
    m = get_molecule(db, molecule_id)
    if not m:
        raise KeyError("Molecule not found")

    batches = db.query(Batch).filter(Batch.molecule_id == molecule_id).order_by(Batch.created_at.desc()).all()
    data_records = (
        db.query(DataRecord)
        .filter(DataRecord.molecule_id == molecule_id)
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .limit(50)
        .all()
    )
    evidence = (
        db.query(Evidence)
        .filter(Evidence.molecule_id == molecule_id)
        .order_by(Evidence.created_at.desc())
        .limit(50)
        .all()
    )

    file_links = db.query(FileLink).filter(FileLink.entity_type == "Molecule", FileLink.entity_id == molecule_id).all()
    file_ids = [fl.file_id for fl in file_links]
    files = db.query(StoredFile).filter(StoredFile.id.in_(file_ids)).all() if file_ids else []
    files_by_id = {f.id: f for f in files}

    audits = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == "Molecule", AuditEvent.entity_id == molecule_id)
        .order_by(AuditEvent.timestamp.desc())
        .all()
    )

    # Computed results (latest + history)
    runs = get_property_runs(db, molecule_id)
    latest_run = runs[0] if runs else None
    latest_values = get_run_values(db, latest_run.id) if latest_run else []
    parsed_values = []
    by_key = {}
    for v in latest_values:
        try:
            parsed = json.loads(v.value_json) if v.value_json else None
        except Exception:
            parsed = v.value_json
        item = {"key": v.property_key, "label": v.label, "value": parsed, "tier": v.tier}
        parsed_values.append(item)
        by_key[v.property_key] = item

    components = db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == molecule_id).all()

    # Heavy compute gating (UI-facing).
    fmt = (m.molecule_format or "").strip()
    heavy_gate_overall = heavy_compute_available_for_molecule(m)
    heavy_gate_domains = heavy_compute_available_for_molecule(m, require=() if fmt == "scFv" else ("anarci", "biopython"))
    heavy_gate_numbering = heavy_compute_available_for_molecule(m, require=("abnumber", "biopython"))

    domain_instances = (
        db.query(DomainInstance)
        .filter(DomainInstance.molecule_id == molecule_id)
        .order_by(DomainInstance.component_id.asc(), DomainInstance.domain_type.asc())
        .all()
    )

    # --- UI feature tracks (Domains + reference matches, incremental) ---
    di_by_component: dict[int, list[DomainInstance]] = {}
    for di in domain_instances:
        di_by_component.setdefault(int(di.component_id), []).append(di)

    feature_tracks = []
    for c in components:
        seq = c.fasta or ""
        lanes = []

        # Lane: extracted domains (DomainInstance)
        dom_features = []
        for di in di_by_component.get(int(c.id), []):
            dom_features.append(
                {
                    "id": f"di:{di.id}",
                    "name": di.domain_type,
                    "feature_type": "domain_instance",
                    "start_idx": int(di.start_idx),
                    "end_idx": int(di.end_idx),
                    "source": di.source,
                    "status": di.status,
                    "method": di.method,
                    "tool_name": di.tool_name,
                    "tool_version": di.tool_version,
                    "meta": {"error": di.error} if di.error else {},
                }
            )
        if dom_features:
            lanes.append({"lane_name": "Domains", "features": dom_features})

        # Lane: PD-L1 approximate match
        ref_features = []
        for rf in detect_pdl1_features(seq=seq, allowed_mismatches=int(pdl1_allowed_mismatches or 0)):
            ref_features.append(
                {
                    "id": f"ref:{c.id}:{rf.feature_type}:{rf.start_idx}:{rf.end_idx}:{rf.name}",
                    "name": rf.name,
                    "feature_type": rf.feature_type,
                    "start_idx": int(rf.start_idx),
                    "end_idx": int(rf.end_idx),
                    "source": "computed",
                    "status": "success",
                    "method": rf.method,
                    "tool_name": rf.tool_name,
                    "tool_version": rf.tool_version,
                    "parent_id": rf.parent_id,
                    "meta": rf.meta or {},
                }
            )
        if ref_features:
            lanes.append({"lane_name": "Reference matches", "features": ref_features})

        feature_tracks.append(
            {
                "component_id": int(c.id),
                "role": c.role,
                "sequence": seq,
                "length": len(seq),
                "lanes": lanes,
            }
        )

    # Latest run logs (for troubleshooting)
    run_events = []
    if latest_run:
        run_events = (
            db.query(PropertyRunEvent)
            .filter(PropertyRunEvent.run_id == latest_run.id)
            .order_by(PropertyRunEvent.timestamp.asc(), PropertyRunEvent.id.asc())
            .all()
        )

    # Manual numbering cache (default scheme kabat for display)
    numbering_payload = get_numbering_artifacts_for_molecule(db, molecule_id=molecule_id, scheme="kabat")

    # Normalized numbering maps for UI (Viewer v2 lane + wrapped "Numbering map")
    # Canonical form: per domain instance -> labels_by_raw_index + mapping back to component raw indices.
    numbering_maps = []
    for c in components:
        comp_id = int(c.id)
        comp_seq = c.fasta or ""
        for di in di_by_component.get(comp_id, []):
            if di.domain_type not in ["VH", "VL"]:
                continue
            start = int(di.start_idx)
            end = int(di.end_idx)
            dom_seq = comp_seq[start:end]
            payload = numbering_payload.get(di.domain_type) if isinstance(numbering_payload, dict) else None
            labels = payload.get("labels_by_raw_index") if isinstance(payload, dict) and payload else None
            numbering_maps.append(
                {
                    "component_id": comp_id,
                    "component_role": c.role,
                    "domain_type": di.domain_type,
                    "start_idx": start,
                    "end_idx": end,
                    "sequence": dom_seq,
                    "scheme": (payload.get("scheme") if isinstance(payload, dict) else None) or "kabat",
                    "tool_name": "abnumber",
                    "tool_version": "",
                    "cache_state": "success" if labels else ("pending" if numbering_payload.get("pending") else "missing"),
                    "labels_by_raw_index": labels or [],
                    "cdrs": (payload.get("cdrs") if isinstance(payload, dict) else None) or {},
                    "warnings": (payload.get("warnings") if isinstance(payload, dict) else None) or [],
                }
            )

    # --- Viewer v2 payload (text-first + aligned numbering + grouped features) ---
    viewer_v2_components = []
    for t in feature_tracks:
        length = int(t["length"])
        seq = t["sequence"]
        comp_id = int(t["component_id"])

        # Raw index labels (1-based, per residue)
        raw_labels = [str(i + 1) for i in range(length)]

        # Antibody numbering labels (only within VH/VL spans when available)
        ab_labels = ["" for _ in range(length)]
        for di in di_by_component.get(comp_id, []):
            if di.domain_type not in ["VH", "VL"]:
                continue
            payload = numbering_payload.get(di.domain_type)
            if not payload:
                continue
            labels = payload.get("labels_by_raw_index") if isinstance(payload, dict) else None
            if not labels:
                continue
            start = int(di.start_idx)
            for i, lab in enumerate(labels):
                pos = start + i
                if 0 <= pos < length and lab:
                    ab_labels[pos] = str(lab)

        has_ab_numbering = any(bool(x) for x in ab_labels)

        # Build unified features[] (multi-span ready)
        # NOTE: This payload is schema-free; DomainInstance remains the only user-editable
        # persisted label mechanism.
        features = []

        # Always-present: full sequence feature
        features.append(
            {
                "id": f"whole:{comp_id}",
                "name": "Full sequence",
                "group": "Sequence",
                "kind": "whole",
                "feature_type": "whole",
                "spans": [{"start": 0, "end": length}],
                "confidence": 1.0,
                "source": "always",
                "status": "success",
                "method": "identity",
                "tool_name": "",
                "tool_version": "",
                "meta": {},
                "parent_id": None,
            }
        )

        # Domains (user-editable spans)
        for di in di_by_component.get(comp_id, []):
            features.append(
                {
                    "id": f"di:{di.id}",
                    "name": di.domain_type,
                    "group": "Recognized regions",
                    "kind": "domain",
                    "feature_type": "domain",
                    "spans": [{"start": int(di.start_idx), "end": int(di.end_idx)}],
                    "confidence": 1.0,
                    "source": di.source,
                    "status": di.status,
                    "method": di.method,
                    "tool_name": di.tool_name,
                    "tool_version": di.tool_version,
                    "meta": {"error": di.error} if di.error else {},
                    "parent_id": None,
                }
            )

        # Fc anchoring (FAST, reference-anchored). Only emits when very confident.
        fc = detect_fc_region(seq)
        if fc:
            features.append(
                {
                    "id": f"fc:{comp_id}:{fc.start}:{fc.end}",
                    "name": fc.name,
                    "group": "Recognized regions",
                    "kind": fc.kind,
                    "feature_type": "region",
                    "spans": [{"start": int(fc.start), "end": int(fc.end)}],
                    "confidence": float(fc.confidence),
                    "source": fc.source,
                    "status": "success",
                    "method": fc.method,
                    "tool_name": fc.tool_name,
                    "tool_version": fc.tool_version,
                    "meta": fc.meta or {},
                    "parent_id": None,
                }
            )

        # Reference matches (PD-L1 only for now)
        for rf in detect_pdl1_features(seq=seq, allowed_mismatches=int(pdl1_allowed_mismatches or 0)):
            if rf.feature_type == "reference_match":
                mm = int(rf.meta.get("mismatches_total", 0))
                ln = int(rf.meta.get("reference_length", max(1, rf.end_idx - rf.start_idx)))
                conf = _confidence_from_mismatches(mm, ln)
            else:
                mm = int(rf.meta.get("mismatches", 0))
                ln = max(1, int(rf.end_idx - rf.start_idx))
                conf = _confidence_from_mismatches(mm, ln)
            features.append(
                {
                    "id": f"ref:{comp_id}:{rf.feature_type}:{rf.start_idx}:{rf.end_idx}:{rf.name}",
                    "name": rf.name,
                    "group": "Recognized regions",
                    "kind": "reference",
                    "feature_type": rf.feature_type,
                    "spans": [{"start": int(rf.start_idx), "end": int(rf.end_idx)}],
                    "confidence": conf,
                    "source": "computed",
                    "status": "success",
                    "method": rf.method,
                    "tool_name": rf.tool_name,
                    "tool_version": rf.tool_version,
                    "parent_id": rf.parent_id,
                    "meta": rf.meta or {},
                }
            )

        # Linkers / junctions (heuristics; conservative)
        for lf in dedupe_features(detect_linker_spans(seq)):
            features.append(
                {
                    "id": f"linker:{comp_id}:{lf.start}:{lf.end}",
                    "name": lf.name,
                    "group": "Linkers / junctions",
                    "kind": lf.kind,
                    "feature_type": "linker",
                    "spans": [{"start": int(lf.start), "end": int(lf.end)}],
                    "confidence": float(lf.confidence),
                    "source": lf.source,
                    "status": "success",
                    "method": lf.method,
                    "tool_name": lf.tool_name,
                    "tool_version": lf.tool_version,
                    "meta": lf.meta or {},
                    "parent_id": None,
                }
            )

        # Motifs / liabilities (FAST)
        for hit in liability_sites(seq):
            features.append(
                {
                    "id": f"motif:{comp_id}:{hit.get('type')}:{hit.get('start')}:{hit.get('end')}",
                    "name": hit.get("type", "motif"),
                    "group": "Motifs / liabilities",
                    "kind": "motif",
                    "feature_type": "motif",
                    "spans": [{"start": int(hit.get("start", 0)), "end": int(hit.get("end", 0))}],
                    "confidence": 1.0,
                    "source": "computed",
                    "status": "success",
                    "method": "liability_sites",
                    "tool_name": "psi_biochem",
                    "tool_version": "v1",
                    "meta": {k: v for k, v in hit.items() if k not in ("start", "end")},
                    "parent_id": None,
                }
            )

        # Stable, grouped presentation for the Annotations panel.
        order = [
            "Sequence",
            "Recognized regions",
            "Linkers / junctions",
            "Engineering features",
            "Motifs / liabilities",
            "Diagnostics",
        ]
        grouped: dict[str, list[dict]] = {}
        for feat in features:
            grouped.setdefault(feat.get("group") or "Other", []).append(feat)
        annotations_groups = []
        for gname in order:
            items = grouped.get(gname, [])
            if not items:
                continue
            # Sort within group by first span start, then name
            def _key(f):
                sp = (f.get("spans") or [{}])[0]
                return (int(sp.get("start", 0)), int(sp.get("end", 0)), str(f.get("name") or ""))

            items_sorted = sorted(items, key=_key)
            annotations_groups.append({"group": gname, "items": items_sorted})

        viewer_v2_components.append(
            {
                "component_id": comp_id,
                "role": t["role"],
                "sequence": seq,
                "length": length,
                "raw_labels": raw_labels,
                "ab_labels": ab_labels,
                "has_ab_numbering": has_ab_numbering,
                "features": features,
                "annotations_groups": annotations_groups,
            }
        )

    return {
        "molecule": m,
        "batches": batches,
        "data_records": data_records,
        "evidence": evidence,
        "file_links": file_links,
        "files_by_id": files_by_id,
        "audits": audits,
        "components": components,
        "heavy_gate_overall": heavy_gate_overall,
        "heavy_gate_domains": heavy_gate_domains,
        "heavy_gate_numbering": heavy_gate_numbering,
        "domain_instances": domain_instances,
        "latest_run_events": run_events,
        "numbering_payload": numbering_payload,
        "numbering_maps": numbering_maps,
        "feature_tracks": feature_tracks,
        "viewer_v2_components": viewer_v2_components,
        "pdl1_allowed_mismatches": int(pdl1_allowed_mismatches or 0),
        "property_runs": runs,
        "latest_run": latest_run,
        "latest_values": latest_values,
        "latest_values_parsed": parsed_values,
        "latest_values_by_key": by_key,
    }


def _background_compute(molecule_id: int, trigger_reason: str) -> None:
    """Run computed properties in a fresh session (for BackgroundTasks)."""
    db = SessionLocal()
    try:
        import os

        m = db.get(Molecule, molecule_id)
        heavy_global = os.getenv("PSI_ENABLE_HEAVY_COMPUTE", "").strip() == "1"
        tier = "FAST+HEAVY" if heavy_global and m and int(m.heavy_compute_enabled or 0) == 1 else "FAST"
        run_computed_properties(db, molecule_id=molecule_id, trigger_reason=trigger_reason, compute_tier=tier)
    finally:
        db.close()


def _background_domain_extraction(molecule_id: int) -> None:
    db = SessionLocal()
    try:
        extract_domains_for_molecule(db, molecule_id)
    finally:
        db.close()


def create_molecule(
    db: Session,
    *,
    program_id: int,
    primary_id: str,
    title: str = "",
    description: str = "",  # legacy form field; treated as user override
    sequences: str = "",  # legacy/unstructured only
    molecule_format: str | None = None,
    description_user: str | None = None,
    heavy_compute_enabled: int = 0,
    components: dict[str, str] | None = None,
    background_tasks=None,
) -> Molecule:
    # Backward compatibility: keep Molecule.description populated with user description.
    desc_user = (description_user if description_user is not None else description).strip() or None

    m = Molecule(
        program_id=program_id,
        primary_id=primary_id.strip(),
        title=title.strip() or None,
        description=desc_user,
        description_user=desc_user,
        molecule_format=(molecule_format or None),
        heavy_compute_enabled=int(heavy_compute_enabled or 0),
        sequences=None,
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(m)
    db.commit()
    db.refresh(m)

    # Structured components (v1.01)
    if components:
        for role, fasta in components.items():
            fasta_n = normalize_aa_sequence(fasta)
            if not fasta_n:
                continue
            c = MoleculeComponent(
                molecule_id=m.id,
                role=role,
                fasta=fasta_n,
                sha256=sha256_text(fasta_n),
                created_at=now_utc(),
                updated_at=now_utc(),
            )
            db.add(c)
        db.commit()

        # Ensure legacy sequences blob remains populated (derived multi-FASTA)
        ordered = []
        for role in ["HC1", "LC1", "HC2", "LC2", "VH", "VL", "linker", "fusion"]:
            if role in components and normalize_aa_sequence(components.get(role, "")):
                ordered.append((role, components[role]))
        m.sequences = to_fasta(ordered).strip() or None
        db.add(m)
        db.commit()
    else:
        # Legacy/unstructured path
        m.sequences = sequences.strip() or None
        db.add(m)
        db.commit()

    record_audit(db, entity_type="Molecule", entity_id=m.id, action="create", before=None, after=model_to_dict(m))
    db.commit()

    # Auto-run computed properties
    if background_tasks is not None:
        background_tasks.add_task(_background_compute, m.id, "molecule_created")
        background_tasks.add_task(_background_domain_extraction, m.id)
    return m


def update_molecule(
    db: Session,
    *,
    molecule_id: int,
    program_id: int,
    primary_id: str,
    title: str = "",
    description: str = "",  # legacy field; treated as user override
    sequences: str = "",  # legacy/unstructured only
    molecule_format: str | None = None,
    description_user: str | None = None,
    heavy_compute_enabled: int = 0,
    components: dict[str, str] | None = None,
    background_tasks=None,
    reason: str = "",
) -> Molecule:
    m = get_molecule(db, molecule_id)
    if not m:
        raise KeyError("Molecule not found")
    before = model_to_dict(m)
    m.program_id = program_id
    m.primary_id = primary_id.strip()
    m.title = title.strip() or None
    desc_user = (description_user if description_user is not None else description).strip() or None
    m.description = desc_user
    m.description_user = desc_user
    m.molecule_format = (molecule_format or None)
    m.heavy_compute_enabled = int(heavy_compute_enabled or 0)

    sequences_changed = False

    if components is not None:
        # Replace/update components per role (additive, role-unique)
        existing = {c.role: c for c in db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()}
        for role in list(existing.keys()):
            if role not in components:
                # Do not delete automatically; keep additive. User can clear by setting empty.
                pass
        for role, fasta in components.items():
            fasta_n = normalize_aa_sequence(fasta)
            if not fasta_n:
                # If user cleared a role, keep existing record but blank? safer: set fasta empty? no, keep as is.
                continue
            if role in existing:
                if existing[role].fasta != fasta_n:
                    existing[role].fasta = fasta_n
                    existing[role].sha256 = sha256_text(fasta_n)
                    existing[role].updated_at = now_utc()
                    db.add(existing[role])
                    sequences_changed = True
            else:
                db.add(
                    MoleculeComponent(
                        molecule_id=m.id,
                        role=role,
                        fasta=fasta_n,
                        sha256=sha256_text(fasta_n),
                        created_at=now_utc(),
                        updated_at=now_utc(),
                    )
                )
                sequences_changed = True
        db.commit()

        # Regenerate legacy sequences field (derived multi-FASTA) for compatibility
        comps_now = db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()
        ordered = []
        for role in ["HC1", "LC1", "HC2", "LC2", "VH", "VL", "linker", "fusion"]:
            for c in comps_now:
                if c.role == role and c.fasta:
                    ordered.append((c.role, c.fasta))
        new_sequences = to_fasta(ordered).strip() or None
        if (m.sequences or "") != (new_sequences or ""):
            m.sequences = new_sequences
            sequences_changed = True
    else:
        # Legacy/unstructured edit
        new_sequences = sequences.strip() or None
        if (m.sequences or "") != (new_sequences or ""):
            sequences_changed = True
        m.sequences = new_sequences

    m.updated_at = now_utc()
    db.add(m)
    db.commit()
    record_audit(
        db,
        entity_type="Molecule",
        entity_id=m.id,
        action="update",
        before=before,
        after=model_to_dict(m),
        reason=reason or None,
    )
    db.commit()

    if sequences_changed and background_tasks is not None:
        background_tasks.add_task(_background_compute, m.id, "molecule_sequences_changed")
        background_tasks.add_task(_background_domain_extraction, m.id)
    return m



def get_molecule_experimental_context(db: Session, molecule_id: int, *, selected_batch_id: int | None = None) -> dict:
    """Batch-first experimental view context for molecule detail.

    v1.1.6 update:
    - Provide ALL batch-linked records (not just selected batch) so the molecule page can render
      a nested, glanceable Batch → Assay → Condition → Runs tree.
    - Keep schema flexibility by using existing DataRecord.params_json for structured conditions.
    - Notes remain free-form and are displayed at the run level.
    """
    import json as _json

    m = get_molecule(db, molecule_id)
    if not m:
        raise KeyError("Molecule not found")

    batches = db.query(Batch).filter(Batch.molecule_id == molecule_id).order_by(Batch.created_at.desc()).all()

    def _load(s: str | None) -> dict:
        try:
            return _json.loads(s) if s else {}
        except Exception:
            return {}

    def _summary_for(r: DataRecord) -> dict:
        res = _load(r.results_json)
        if r.data_type == "CMC_Analytics" and r.method in ("SEC_HPLC", "SEC"):
            return {
                "kind": "SEC",
                "monomer_pct": res.get("monomer_pct"),
                "hmw_pct": res.get("hmw_pct"),
                "lmw_pct": res.get("lmw_pct"),
                "rt_monomer_min": res.get("rt_monomer_min"),
            }
        if r.data_type == "CMC_Analytics" and r.method == "Endotoxin":
            return {
                "kind": "Endotoxin",
                "value_eu_ml": res.get("value_eu_ml"),
                "limit_eu_ml": res.get("limit_eu_ml"),
            }
        if r.data_type == "Binding" and r.method in ("BLI", "SPR"):
            return {
                "kind": "Binding",
                "kd_nM": res.get("kd_nM"),
                "kon": res.get("kon"),
                "koff": res.get("koff"),
                "chi2": res.get("chi2") or res.get("fit_quality"),
            }
        return {"kind": "Other"}

    def _assay_bucket(r: DataRecord) -> str:
        # UI-facing buckets. Keep descriptive, not interpretive.
        if r.data_type == "CMC_Analytics" and r.method in ("SEC_HPLC", "SEC"):
            return "SEC"
        if r.data_type == "Binding" and r.method in ("SPR", "BLI"):
            return "Binding"
        if r.data_type == "CMC_Analytics" and r.method == "Endotoxin":
            return "Endotoxin"
        # Fall back to type/method (still useful).
        return f"{r.data_type}/{r.method}"

    def _normalize_params(p: dict) -> dict:
        # Remove empty strings/nulls for stable grouping.
        out = {}
        for k, v in (p or {}).items():
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            out[k] = v
        return out

    def _fingerprint(p: dict) -> str:
        try:
            norm = _normalize_params(p)
            return _json.dumps(norm, sort_keys=True, separators=(",", ":"))
        except Exception:
            return ""

    def _condition_label(r: DataRecord, p: dict) -> str:
        # Human label for the third-level grouping under an assay bucket.
        # Prefer structured fields; fall back to legacy fields.
        if r.data_type == "CMC_Analytics" and r.method in ("SEC_HPLC", "SEC"):
            buf = (p.get("buffer") or p.get("mobile_phase") or "").strip()
            salt = p.get("salt_mM")
            salt_type = p.get("salt_type") or "NaCl"
            parts = []
            if buf:
                parts.append(buf)
            if salt not in (None, "", 0, "0"):
                try:
                    parts.append(f"+ {int(float(salt))} mM {salt_type}")
                except Exception:
                    parts.append(f"+ {salt} mM {salt_type}")
            if not parts:
                parts.append("Unspecified condition")
            return " ".join(parts)

        if r.data_type == "Binding" and r.method in ("SPR", "BLI"):
            ligand = (p.get("ligand") or "").strip()
            analyte = (p.get("analyte") or "").strip()
            buf = (p.get("buffer") or "").strip()
            parts = []
            if ligand and analyte:
                parts.append(f"{r.method} — {ligand} vs {analyte}")
            elif ligand:
                parts.append(f"{r.method} — {ligand}")
            elif analyte:
                parts.append(f"{r.method} — {analyte}")
            else:
                parts.append(f"{r.method}")
            if buf:
                parts.append(f"({buf})")
            return " ".join(parts)

        if r.data_type == "CMC_Analytics" and r.method == "Endotoxin":
            matrix = (p.get("sample_matrix") or p.get("buffer") or "").strip()
            return f"Matrix: {matrix}" if matrix else "Endotoxin"

        return "Condition"

    def _batch_tree_for(batch: Batch) -> dict:
        # Pull enough history to be useful without going unbounded.
        recs: list[DataRecord] = (
            db.query(DataRecord)
            .filter(DataRecord.batch_id == batch.id)
            .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
            .limit(500)
            .all()
        )

        # Build: assay -> condition_fp -> {label, runs[]}
        assay_map: dict[str, dict[str, dict]] = {}
        for r in recs:
            p = _load(r.params_json)
            fp = _fingerprint(p)
            assay = _assay_bucket(r)
            cond_label = _condition_label(r, p)

            if assay not in assay_map:
                assay_map[assay] = {}
            if fp not in assay_map[assay]:
                assay_map[assay][fp] = {"label": cond_label, "params": _normalize_params(p), "runs": []}

            assay_map[assay][fp]["runs"].append(
                {
                    "record": r,
                    "params": _normalize_params(p),
                    "summary": _summary_for(r),
                }
            )

        # Create small "glance" summaries per assay+condition
        glance: dict[str, list[str]] = {}
        for assay, conds in assay_map.items():
            glance[assay] = []
            for fp, node in conds.items():
                runs = node["runs"]
                if not runs:
                    continue
                # For known assays, show result-first summaries that remain descriptive.
                first = runs[0]
                s = first.get("summary") or {}
                label = node["label"]
                if s.get("kind") == "SEC":
                    # Show monomer/hmw/lmw. If multiple runs, show range on monomer.
                    monos = [rr.get("summary", {}).get("monomer_pct") for rr in runs]
                    monos = [x for x in monos if x is not None]
                    if len(monos) >= 2:
                        try:
                            lo = min(float(x) for x in monos)
                            hi = max(float(x) for x in monos)
                            mono_txt = f"{lo:.1f}–{hi:.1f}% monomer"
                        except Exception:
                            mono_txt = f"{monos[0]}% monomer"
                    elif len(monos) == 1:
                        mono_txt = f"{monos[0]}% monomer"
                    else:
                        mono_txt = "monomer n/a"
                    hmw = s.get("hmw_pct")
                    lmw = s.get("lmw_pct")
                    parts = [mono_txt]
                    if hmw is not None:
                        parts.append(f"{hmw}% HMW")
                    if lmw is not None:
                        parts.append(f"{lmw}% LMW")
                    glance[assay].append(f"{label}: " + " / ".join(parts) + f" (n={len(runs)})")
                elif s.get("kind") == "Binding":
                    kd = s.get("kd_nM")
                    if kd is not None:
                        glance[assay].append(f"{label}: KD {kd} nM (n={len(runs)})")
                    else:
                        glance[assay].append(f"{label}: KD n/a (n={len(runs)})")
                elif s.get("kind") == "Endotoxin":
                    val = s.get("value_eu_ml")
                    lim = s.get("limit_eu_ml")
                    if val is not None and lim is not None:
                        glance[assay].append(f"{label}: {val} EU/mL (limit {lim}) (n={len(runs)})")
                    else:
                        glance[assay].append(f"{label} (n={len(runs)})")
                else:
                    glance[assay].append(f"{label} (n={len(runs)})")

        return {
            "batch": batch,
            "assays": assay_map,
            "glance": glance,
            "record_count": len(recs),
        }

    batch_panels = [_batch_tree_for(b) for b in batches]

    # Also provide molecule-level records not linked to a batch (still important sometimes).
    molecule_level_records: list[DataRecord] = (
        db.query(DataRecord)
        .filter(DataRecord.molecule_id == molecule_id)
        .filter(DataRecord.batch_id.is_(None))
        .order_by(DataRecord.run_date.desc().nullslast(), DataRecord.created_at.desc())
        .limit(200)
        .all()
    )
    molecule_level_enriched = [{"record": r, "summary": _summary_for(r), "params": _normalize_params(_load(r.params_json))} for r in molecule_level_records]

    return {
        "exp_batches": batches,
        "exp_batch_panels": batch_panels,
        "exp_molecule_level_records": molecule_level_enriched,
        # Legacy keys kept for backwards compatibility with older templates (safe to remove later):
        "exp_selected_batch": None,
        "exp_records": [],
        "exp_latest_sec": None,
        "exp_latest_binding": None,
        "exp_latest_endotoxin": None,
    }
