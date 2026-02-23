from __future__ import annotations

import re

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Any

from psi.core.audit import record_audit
from psi.core.models import (
    SequenceEntity,
    AuditEvent,
    Batch,
    DecisionSnapshot,
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
from psi.services.di.snapshot_diff import compute_snapshot_diff_struct
from psi.core.utils import model_to_dict, now_utc
import json
from psi.core.fasta import normalize_aa_sequence, sha256_text, to_fasta
from psi.core.db import SessionLocal, get_db
from psi.services.computed import run_computed_properties, get_property_runs, get_run_values
from psi.services.domains import extract_domains_for_molecule
from psi.services.numbering import get_numbering_artifacts_for_molecule
from psi.services import qc as qc_svc
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


class DuplicateMoleculeError(Exception):
    def __init__(self, existing_molecule_id: int, existing_primary_id: str):
        super().__init__(f"Molecule already exists as {existing_primary_id}")
        self.existing_molecule_id = int(existing_molecule_id)
        self.existing_primary_id = str(existing_primary_id)


def _next_chain_id(db: Session) -> str:
    """Allocate next CHAINXXX id (local-first, monotonic best-effort)."""
    rows = db.query(SequenceEntity.chain_id).filter(SequenceEntity.chain_id.isnot(None)).all()
    mx = 0
    for (cid,) in rows:
        if not cid:
            continue
        m = re.match(r'^CHAIN(\d+)$', cid)
        if m:
            mx = max(mx, int(m.group(1)))
    return f"CHAIN{mx+1:03d}"


def get_or_create_chain(
    db: Session,
    sequence_text: str,
    *,
    type_hint: str | None = None,
    notes: str | None = None,
) -> SequenceEntity:
    """Global chain registry: de-dupe by sha256(sequence_norm) and ensure CHAINXXX."""
    seq = normalize_aa_sequence(sequence_text or "")
    if not seq:
        raise ValueError("Empty sequence")

    h = sha256_text(seq)
    ent = db.query(SequenceEntity).filter(SequenceEntity.sha256 == h).first()

    if ent is None:
        max_attempts = 3
        for attempt in range(max_attempts):
            ent = SequenceEntity(
                sha256=h,
                sequence_norm=seq,
                length=len(seq),
                alphabet="AA",
                created_at=now_utc(),
            )
            ent.chain_id = _next_chain_id(db)
            if type_hint:
                ent.type_hint = type_hint
            if notes:
                ent.notes = notes
            db.add(ent)
            try:
                db.flush()
                return ent
            except IntegrityError:
                db.rollback()
                if attempt == max_attempts - 1:
                    raise
                ent = db.query(SequenceEntity).filter(SequenceEntity.sha256 == h).first()
                if ent is not None:
                    break

    if not ent.chain_id:
        max_attempts = 3
        for attempt in range(max_attempts):
            ent.chain_id = _next_chain_id(db)
            db.add(ent)
            try:
                db.flush()
                break
            except IntegrityError:
                db.rollback()
                if attempt == max_attempts - 1:
                    raise

    if type_hint and not ent.type_hint:
        ent.type_hint = type_hint
        db.add(ent)
    if notes and not ent.notes:
        ent.notes = notes
        db.add(ent)

    db.flush()
    return ent


def _canonical_composition(chain_by_role: dict[str, str | None]) -> dict[str, str | None]:
    order = ['HC1','HC2','LC1','LC2']
    return {k: chain_by_role.get(k) for k in order}


def composition_sha256(chain_by_role: dict[str, str | None]) -> str:
    import json as _json
    canonical = _canonical_composition(chain_by_role)
    payload = _json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    return sha256_text(payload)


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

    batch_label_by_id = {int(b.id): (str(getattr(b, "batch_id", "") or b.id)) for b in batches}

    # v1.2.9m: molecule-level DI decision history + drift vs previous (read-only)
    snaps = (
        db.query(DecisionSnapshot)
        .filter(DecisionSnapshot.molecule_id == molecule_id)
        .order_by(DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
        .all()
    )

    # We compute drift vs previous snapshot (same decision_key) deterministically using the
    # shared snapshot diff module (no engine/policy changes; UI surface only).
    _tmp: list[dict[str, Any]] = []
    for s in snaps:
        try:
            out = json.loads(s.outputs_json or "{}")
        except Exception:
            out = {}
        try:
            inn = json.loads(s.inputs_json or "{}")
        except Exception:
            inn = {}
        if not isinstance(out, dict) or not out.get("decision_state"):
            continue

        policy = out.get("policy") if isinstance(out.get("policy"), dict) else {}
        prov = out.get("provenance") if isinstance(out.get("provenance"), dict) else {}
        integ = prov.get("integrity") if isinstance(prov.get("integrity"), dict) else {}

        gate_outcomes = out.get("gate_outcomes") if isinstance(out.get("gate_outcomes"), dict) else {}
        if not gate_outcomes and isinstance(out.get("gates"), list):
            gate_outcomes = {
                str(g.get("gate_key")): {"status": g.get("status")}
                for g in out.get("gates")
                if isinstance(g, dict) and g.get("gate_key")
            }
        statuses = [str(v.get("status") or "") for v in (gate_outcomes or {}).values() if isinstance(v, dict)]
        pass_n = sum(1 for x in statuses if x == "pass")
        nonpass_n = sum(1 for x in statuses if x and x != "pass")
        blocker_n = len(out.get("blockers") or []) if isinstance(out.get("blockers"), list) else 0

        _tmp.append(
            {
                "snapshot_id": int(s.id),
                "created_at": s.created_at,
                "decision_key": s.decision_key,
                "batch_id": int(s.batch_id) if s.batch_id is not None else None,
                "batch_label": batch_label_by_id.get(int(s.batch_id or 0), str(s.batch_id or "")) if s.batch_id else "",
                "is_superseded": int(s.is_superseded) if s.is_superseded is not None else None,
                "superseded_by_snapshot_id": int(s.superseded_by_snapshot_id) if s.superseded_by_snapshot_id is not None else None,
                "superseded_at": s.superseded_at,
                "policy_id": str(policy.get("policy_id") or ""),
                "policy_version": str(policy.get("policy_version") or ""),
                "summary": {
                    "decision_state": str(out.get("decision_state") or ""),
                    "gates_pass": int(pass_n),
                    "gates_nonpass": int(nonpass_n),
                    "blockers": int(blocker_n),
                },
                "integrity": {
                    "snapshot_content_hash": str(integ.get("snapshot_content_hash") or ""),
                    "evidence_fingerprint": str(integ.get("evidence_fingerprint") or ""),
                },
                "_out": out,
                "_in": inn,
            }
        )

    # Sort chronologically for "vs previous" computations, then return newest-first for display.
    _tmp_sorted = sorted(_tmp, key=lambda r: (r.get("created_at") or "", int(r.get("snapshot_id") or 0)))
    prev_by_decision_key: dict[str, dict[str, Any]] = {}
    for row in _tmp_sorted:
        dk = str(row.get("decision_key") or "")
        prev = prev_by_decision_key.get(dk)
        if prev is not None:
            try:
                dr = compute_snapshot_diff_struct(
                    out1=prev.get("_out") or {},
                    in1=prev.get("_in") or {},
                    out2=row.get("_out") or {},
                    in2=row.get("_in") or {},
                )
                row["prev_snapshot_id"] = int(prev.get("snapshot_id") or 0)
                row["drift_vs_prev"] = str(dr.drift_label)
            except Exception:
                row["prev_snapshot_id"] = None
                row["drift_vs_prev"] = None
        else:
            row["prev_snapshot_id"] = None
            row["drift_vs_prev"] = None
        prev_by_decision_key[dk] = row

    # Final display ordering: newest first.
    di_history: list[dict[str, Any]] = []
    for row in sorted(_tmp_sorted, key=lambda r: (r.get("created_at") or "", int(r.get("snapshot_id") or 0)), reverse=True):
        row.pop("_out", None)
        row.pop("_in", None)
        di_history.append(row)

    qc_counts_by_batch = qc_svc.get_qc_counts_for_batches(db, molecule_id=molecule_id)

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
    latest_run = None
    latest_immuno_run = None
    for r in runs:
        if (r.compute_tier or "").upper() == "IMMUNO" and latest_immuno_run is None:
            latest_immuno_run = r
            continue
        if latest_run is None:
            latest_run = r

    latest_values = get_run_values(db, latest_run.id) if latest_run else []
    immuno_values = get_run_values(db, latest_immuno_run.id) if latest_immuno_run else []
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

    immuno_parsed = []
    immuno_by_key = {}
    for v in immuno_values:
        try:
            parsed = json.loads(v.value_json) if v.value_json else None
        except Exception:
            parsed = v.value_json
        item = {"key": v.property_key, "label": v.label, "value": parsed, "tier": v.tier}
        immuno_parsed.append(item)
        immuno_by_key[v.property_key] = item

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
        "di_history": di_history,
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
        "latest_immuno_run": latest_immuno_run,
        "immuno_values": immuno_values,
        "immuno_values_parsed": immuno_parsed,
        "immuno_values_by_key": immuno_by_key,
    }


def _background_compute(molecule_id: int, trigger_reason: str, db_path: str | None = None) -> None:
    """Run computed properties in a fresh session (for BackgroundTasks)."""
    import os

    if db_path:
        with get_db(db_path, ensure=False) as db:
            m = db.get(Molecule, molecule_id)
            heavy_global = os.getenv("PSI_ENABLE_HEAVY_COMPUTE", "").strip() == "1"
            tier = "FAST+HEAVY" if heavy_global and m and int(m.heavy_compute_enabled or 0) == 1 else "FAST"
            run_computed_properties(db, molecule_id=molecule_id, trigger_reason=trigger_reason, compute_tier=tier)
        return

    db = SessionLocal()
    try:
        m = db.get(Molecule, molecule_id)
        heavy_global = os.getenv("PSI_ENABLE_HEAVY_COMPUTE", "").strip() == "1"
        tier = "FAST+HEAVY" if heavy_global and m and int(m.heavy_compute_enabled or 0) == 1 else "FAST"
        run_computed_properties(db, molecule_id=molecule_id, trigger_reason=trigger_reason, compute_tier=tier)
    finally:
        db.close()


def _background_domain_extraction(molecule_id: int, db_path: str | None = None) -> None:
    if db_path:
        with get_db(db_path, ensure=False) as db:
            extract_domains_for_molecule(db, molecule_id)
        return

    db = SessionLocal()
    try:
        extract_domains_for_molecule(db, molecule_id)
    finally:
        db.close()


def _next_molecule_primary_id(db: Session) -> str:
    """Allocate next TCBXXX id (best-effort)."""
    pat = re.compile(r"^TCB(\d{3})$")
    max_n = 0
    rows = db.query(Molecule.primary_id).all()
    for (pid,) in rows:
        if not pid:
            continue
        mm = pat.match(str(pid).strip())
        if mm:
            max_n = max(max_n, int(mm.group(1)))
    return f"TCB{max_n + 1:03d}"


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
    db_path: str | None = None,
) -> Molecule:
    """Create a molecule.

    v1.2.0 semantics:
    - Molecule identity is the canonical HC/LC role->CHAIN mapping (composition_sha256)
    - Chains are globally de-duped via SequenceEntity (sha256)
    - Duplicate molecule compositions are blocked
    """
    # Backward compatibility: keep Molecule.description populated with user description.
    desc_user = (description_user if description_user is not None else description).strip() or None

    pid = (primary_id or "").strip()
    auto_primary = not pid
    max_attempts = 3 if auto_primary else 1

    for attempt in range(max_attempts):
        if not pid:
            pid = _next_molecule_primary_id(db)

        try:
            # Create molecule row early (but don't commit until collision check passes)
            m = Molecule(
                program_id=program_id,
                primary_id=pid,
                title=title.strip() or None,
                description=desc_user,
                description_user=desc_user,
                molecule_format=(molecule_format or None),
                heavy_compute_enabled=int(heavy_compute_enabled or 0),
                sequences=None,
                created_at=now_utc(),
                updated_at=now_utc(),
            )

            # Structured components are the v1.2.0 source of truth. Legacy `sequences` remains populated.
            role_order = ["HC1", "HC2", "LC1", "LC2"]
            role_to_seq: dict[str, str] = {}

            if components:
                # Only accept v1.2.0 user roles; ignore others (legacy remains readable).
                for r in role_order:
                    if r in components:
                        role_to_seq[r] = components.get(r, "") or ""

                # Default infer: HC2=HC1, LC2=LC1 when blank.
                hc1 = normalize_aa_sequence(role_to_seq.get("HC1", ""))
                lc1 = normalize_aa_sequence(role_to_seq.get("LC1", ""))
                if not hc1 or not lc1:
                    raise ValueError("HC1 and LC1 are required for structured molecule creation")

                hc2 = normalize_aa_sequence(role_to_seq.get("HC2", "")) or hc1
                lc2 = normalize_aa_sequence(role_to_seq.get("LC2", "")) or lc1

                role_to_seq = {"HC1": hc1, "HC2": hc2, "LC1": lc1, "LC2": lc2}

                # Chain registry + composition hash
                chains_by_role: dict[str, str | None] = {}
                ents_by_role = {}
                for role, seq in role_to_seq.items():
                    ent = get_or_create_chain(db, seq)
                    ents_by_role[role] = ent
                    chains_by_role[role] = getattr(ent, "chain_id", None)

                comp_hash = composition_sha256(chains_by_role)
                # Collision check (block creation)
                existing = db.query(Molecule).filter(Molecule.composition_sha256 == comp_hash).first()
                if existing is not None:
                    raise DuplicateMoleculeError(existing_molecule_id=existing.id, existing_primary_id=existing.primary_id)

                m.composition_sha256 = comp_hash

                # Populate legacy multi-FASTA
                m.sequences = to_fasta([(r, role_to_seq[r]) for r in role_order]).strip() or None

                db.add(m)
                db.flush()  # assign id

                # Create components as join records
                for role in role_order:
                    seq = role_to_seq[role]
                    ent = ents_by_role[role]
                    c = MoleculeComponent(
                        molecule_id=m.id,
                        role=role,
                        fasta=seq,
                        sha256=sha256_text(seq),
                        sequence_entity_id=ent.id,
                        created_at=now_utc(),
                        updated_at=now_utc(),
                    )
                    db.add(c)

                db.commit()
                db.refresh(m)
            else:
                # Legacy/unstructured path (no collision semantics)
                m.sequences = sequences.strip() or None
                db.add(m)
                db.commit()
                db.refresh(m)

            record_audit(db, entity_type="Molecule", entity_id=m.id, action="create", before=None, after=model_to_dict(m))
            db.commit()

            # Auto-run computed properties
            if background_tasks is not None:
                background_tasks.add_task(_background_compute, m.id, "molecule_created", db_path)
                background_tasks.add_task(_background_domain_extraction, m.id, db_path)
            return m
        except IntegrityError:
            db.rollback()
            db.expunge_all()
            if attempt == max_attempts - 1:
                raise
            pid = ""
            continue


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
    db_path: str | None = None,
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
        # v1.2.0: only accept HC/LC user roles for structured edits.
        role_order = ["HC1", "HC2", "LC1", "LC2"]

        # Collect requested structured roles from the incoming payload.
        requested = {r: (components.get(r, "") or "") for r in role_order if r in components}

        # If the form submitted any of the structured roles, treat this as a structured edit.
        if any(r in requested for r in ["HC1", "LC1", "HC2", "LC2"]):
            hc1 = normalize_aa_sequence(requested.get("HC1", ""))
            lc1 = normalize_aa_sequence(requested.get("LC1", ""))
            if not hc1 or not lc1:
                raise ValueError("HC1 and LC1 are required for structured molecule editing")

            hc2 = normalize_aa_sequence(requested.get("HC2", "")) or hc1
            lc2 = normalize_aa_sequence(requested.get("LC2", "")) or lc1

            role_to_seq = {"HC1": hc1, "HC2": hc2, "LC1": lc1, "LC2": lc2}

            # Chain registry + composition hash
            chains_by_role: dict[str, str | None] = {}
            ents_by_role = {}
            for role, seq in role_to_seq.items():
                ent = get_or_create_chain(db, seq)
                ents_by_role[role] = ent
                chains_by_role[role] = getattr(ent, "chain_id", None)

            comp_hash = composition_sha256(chains_by_role)
            existing = db.query(Molecule).filter(Molecule.composition_sha256 == comp_hash, Molecule.id != m.id).first()
            if existing is not None:
                raise DuplicateMoleculeError(existing_molecule_id=existing.id, existing_primary_id=existing.primary_id)

            m.composition_sha256 = comp_hash

            # Update components (role-unique)
            existing_components = {c.role: c for c in db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()}
            for role in role_order:
                seq = role_to_seq[role]
                ent = ents_by_role[role]
                if role in existing_components:
                    c = existing_components[role]
                    if c.fasta != seq or c.sequence_entity_id != ent.id:
                        c.fasta = seq
                        c.sha256 = sha256_text(seq)
                        c.sequence_entity_id = ent.id
                        c.updated_at = now_utc()
                        db.add(c)
                        sequences_changed = True
                else:
                    db.add(
                        MoleculeComponent(
                            molecule_id=m.id,
                            role=role,
                            fasta=seq,
                            sha256=sha256_text(seq),
                            sequence_entity_id=ent.id,
                            created_at=now_utc(),
                            updated_at=now_utc(),
                        )
                    )
                    sequences_changed = True

            # Keep legacy FASTA blob populated
            m.sequences = to_fasta([(r, role_to_seq[r]) for r in role_order]).strip() or None
            sequences_changed = True
        else:
            # Additive legacy behavior for non-structured roles (kept for backwards compatibility)
            existing = {c.role: c for c in db.query(MoleculeComponent).filter(MoleculeComponent.molecule_id == m.id).all()}
            for role, fasta in components.items():
                fasta_n = normalize_aa_sequence(fasta)
                if not fasta_n:
                    if role in existing:
                        db.delete(existing[role])
                        sequences_changed = True
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
        background_tasks.add_task(_background_compute, m.id, "molecule_sequences_changed", db_path)
        background_tasks.add_task(_background_domain_extraction, m.id, db_path)
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

    from psi.core import assays as assay_norm

    m = get_molecule(db, molecule_id)
    if not m:
        raise KeyError("Molecule not found")

    batches = db.query(Batch).filter(Batch.molecule_id == molecule_id).order_by(Batch.created_at.desc()).all()

    qc_counts_by_batch = qc_svc.get_qc_counts_for_batches(db, molecule_id=molecule_id)


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
        # UI-facing buckets, normalized via psi.core.assays
        return assay_norm.assay_key(r)

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
                    "result_text": assay_norm.record_result_text(r),
                }
            )

        # Create small "glance" summaries per assay+condition
        glance: dict[str, list[str]] = {}
        for assay, conds in assay_map.items():
            display = assay_norm.assay_display_name(assay)
            glance[display] = []
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
                    glance[display].append(f"{label}: " + " / ".join(parts) + f" (n={len(runs)})")
                elif s.get("kind") == "Binding":
                    kd = s.get("kd_nM")
                    if kd is not None:
                        glance[display].append(f"{label}: KD {kd} nM (n={len(runs)})")
                    else:
                        glance[display].append(f"{label}: KD n/a (n={len(runs)})")
                elif s.get("kind") == "Endotoxin":
                    val = s.get("value_eu_ml")
                    lim = s.get("limit_eu_ml")
                    if val is not None and lim is not None:
                        glance[display].append(f"{label}: {val} EU/mL (limit {lim}) (n={len(runs)})")
                    else:
                        glance[display].append(f"{label} (n={len(runs)})")
                else:
                    glance[display].append(f"{label} (n={len(runs)})")

        return {
            "batch": batch,
            "assays": assay_map,
            "glance": glance,
            "record_count": len(recs),
            "qc": qc_counts_by_batch.get(int(batch.id), {}),
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
    molecule_level_enriched = [{"record": r, "summary": _summary_for(r), "result_text": assay_norm.record_result_text(r), "params": _normalize_params(_load(r.params_json))} for r in molecule_level_records]

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


# ---- v1.2.7: batch-first molecule UI decoration (QC-aware headlines) ----

def _batch_sort_key(batch_id: str) -> tuple:
    """Deterministic batch sort.

    - If batch_id ends with a numeric suffix like '-001', sort by that integer.
    - Otherwise fall back to case-insensitive lexical sort.
    """
    s = (batch_id or "").strip()
    try:
        m = re.search(r"-(\d{1,6})$", s)
    except Exception:
        m = None
    if m:
        try:
            return (0, int(m.group(1)), s.lower())
        except Exception:
            pass
    return (1, s.lower())


def _reflect_measurement_cols(db: Session) -> dict:
    """Best-effort reflection of the data_measurements schema (read-only)."""
    from sqlalchemy import text as _text

    try:
        rows = db.execute(_text("PRAGMA table_info(data_measurements)")).mappings().all()
    except Exception:
        return {}

    cols = {str(r["name"]): True for r in rows}

    def pick(*names: str):
        for n in names:
            if n in cols:
                return n
        return None

    out = {
        "record_fk": pick("data_record_id", "record_id"),
        "name": pick("metric_key", "name", "key"),
        "value_num": pick("value_num", "numeric_value", "value"),
        "value_text": pick("value_text", "text_value", "raw_value"),
        "unit": pick("unit"),
        "comparator": pick("comparator", "op"),
        "is_primary": pick("is_primary", "primary", "is_headline"),
        "is_outlier": pick("is_outlier"),
        "qc_flag": pick("qc_flag", "qc_status"),
        "ignore_for_model": pick("ignore_for_model"),
        "id": pick("id"),
        "created_at": pick("created_at", "updated_at", "timestamp", "ts"),
        "_all": set(cols.keys()),
    }
    if not out["record_fk"] or not out["name"]:
        return {}
    return out


def _fmt_num(v: float, *, sig: int = 3) -> str:
    try:
        x = float(v)
    except Exception:
        return str(v)
    if x == 0:
        return "0"
    try:
        import math

        digits = sig - int(math.floor(math.log10(abs(x)))) - 1
        digits = max(-2, min(6, digits))
        return f"{x:.{digits}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(v)


def _fmt_percent(v: float) -> str:
    try:
        x = float(v)
    except Exception:
        return str(v)
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x))}%"
    return f"{x:.1f}%"


def _match_name(name: str, patterns: list) -> bool:
    if not name:
        return False
    n = str(name).strip().lower()
    for p in patterns:
        if isinstance(p, str):
            if p in n:
                return True
        else:
            try:
                if p.search(n):
                    return True
            except Exception:
                continue
    return False


def _best_measurement(measurements: list[dict], patterns: list) -> dict | None:
    cand = [m for m in measurements if _match_name(m.get("name"), patterns)]
    if not cand:
        return None

    def score(m):
        prim = 1 if (m.get("is_primary") in (1, True, "1")) else 0
        has_num = 1 if (m.get("value_num") is not None) else 0
        mid = m.get("id") or 0
        midn = int(mid) if str(mid).isdigit() else 0
        return (prim, has_num, midn, str(m.get("name") or "").lower())

    cand.sort(key=score, reverse=True)
    return cand[0]


def _headline_items_for_record(measurements: list[dict]) -> list[str]:
    """Return up to 3 headline strings (deterministic) from measurement rows."""
    items: list[str] = []

    purity = _best_measurement(measurements, ["monomer_pct", "purity", "sec_purity", re.compile(r"\bmonomer\b")])
    hmw = _best_measurement(measurements, ["hmw_pct", "sec_hmw", re.compile(r"\bhmw\b")])
    lmw = _best_measurement(measurements, ["lmw_pct", "sec_lmw", re.compile(r"\blmw\b")])
    if purity and purity.get("value_num") is not None:
        items.append(f"Purity {_fmt_percent(purity['value_num'])}")
        if hmw and hmw.get("value_num") is not None:
            items.append(f"HMW {_fmt_percent(hmw['value_num'])}")
        if lmw and lmw.get("value_num") is not None:
            items.append(f"LMW {_fmt_percent(lmw['value_num'])}")

    kd = _best_measurement(measurements, ["kd", "kd_nm", "kd_n", "affinity"])
    ec50 = _best_measurement(measurements, ["ec50"])
    ic50 = _best_measurement(measurements, ["ic50"])
    if kd and kd.get("value_num") is not None and len(items) < 3:
        unit = (kd.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"KD {_fmt_num(kd['value_num'])}{u}")
    if ec50 and ec50.get("value_num") is not None and len(items) < 3:
        unit = (ec50.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"EC50 {_fmt_num(ec50['value_num'])}{u}")
    if ic50 and ic50.get("value_num") is not None and len(items) < 3:
        unit = (ic50.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"IC50 {_fmt_num(ic50['value_num'])}{u}")

    titer = _best_measurement(measurements, ["titer", "expression", "yield", "concentration", "mg/l", "mg/ml"])
    if titer and titer.get("value_num") is not None and len(items) < 3:
        unit = (titer.get("unit") or "").strip()
        u = f" {unit}" if unit else ""
        items.append(f"Titer {_fmt_num(titer['value_num'])}{u}")

    return items[:3]


def _fetch_measurements_for_record(db: Session, record_id: int, cols: dict, *, qc_mode: str = "all") -> list[dict]:
    """Fetch measurement rows for a record with deterministic ordering and optional QC filtering.

    qc_mode:
      - all: legacy behavior (exclude qc_flag if present)
      - model_safe: exclude ignore_for_model=1, ignore_policy!=include, and rejected/quarantined statuses
      - approved: require status==approved and ignore_for_model=0
    """
    if not cols:
        return []

    from sqlalchemy import text as _text

    qc_mode = (qc_mode or "all").strip().lower()
    if qc_mode not in ("all", "model_safe", "approved"):
        qc_mode = "all"

    where = [f"dm.{cols['record_fk']}=:rid"]
    params = {"rid": int(record_id)}

    # Legacy qc_flag filtering (kept for backwards compatibility).
    qc_col = cols.get("qc_flag")
    if qc_col:
        where.append(f"(dm.{qc_col} IS NULL OR dm.{qc_col}=0 OR dm.{qc_col}='0' OR dm.{qc_col}='')")

    # QC-aware selection (measurement_qc is optional; missing rows are treated as unreviewed/include).
    if qc_mode == "model_safe":
        if cols.get("ignore_for_model"):
            where.append(f"(dm.{cols['ignore_for_model']} IS NULL OR dm.{cols['ignore_for_model']}=0)")
        where.append("(mq.ignore_policy IS NULL OR mq.ignore_policy='include')")
        where.append("(mq.status IS NULL OR mq.status NOT IN ('rejected','quarantined'))")
    elif qc_mode == "approved":
        if cols.get("ignore_for_model"):
            where.append(f"(dm.{cols['ignore_for_model']} IS NULL OR dm.{cols['ignore_for_model']}=0)")
        where.append("mq.status='approved'")

    order = []
    if cols.get("is_primary"):
        order.append(f"dm.{cols['is_primary']} DESC")
    if cols.get("created_at"):
        order.append(f"dm.{cols['created_at']} DESC")
    if cols.get("id"):
        order.append(f"dm.{cols['id']} DESC")
    order.append(f"dm.{cols['name']} ASC")

    q = _text(
        f"""
        SELECT dm.*,
               mq.status AS qc_status,
               mq.ignore_policy AS qc_ignore_policy
        FROM data_measurements dm
        LEFT JOIN measurement_qc mq ON mq.measurement_id = dm.id
        WHERE {' AND '.join(where)}
        ORDER BY {', '.join(order)}
        """
    )
    rows = db.execute(q, params).mappings().all()

    out: list[dict] = []

    def get(r, k):
        c = cols.get(k)
        return r.get(c) if c else None

    for r in rows:
        out.append(
            {
                "id": get(r, "id") or r.get("id"),
                "record_id": int(record_id),
                "name": get(r, "name"),
                "value_num": get(r, "value_num"),
                "value_text": get(r, "value_text"),
                "unit": get(r, "unit"),
                "comparator": get(r, "comparator"),
                "is_primary": get(r, "is_primary") or 0,
                "qc_status": r.get("qc_status"),
                "qc_ignore_policy": r.get("qc_ignore_policy"),
            }
        )
    return out


def _latest_record_id(panel: dict) -> int | None:
    """Pick latest record id within a panel (run_date desc, created_at desc, id desc)."""
    best = None
    for _, conds in (panel.get("assays") or {}).items():
        for _, node in (conds or {}).items():
            runs = node.get("runs") or []
            for item in runs:
                r = item.get("record")
                if not r:
                    continue
                key = (0 if r.run_date else 1, str(r.run_date or ""), r.created_at, int(r.id))
                if best is None or key > best[0]:
                    best = (key, int(r.id))
    return best[1] if best else None


def _collect_record_ids_from_panels(panels: list[dict]) -> list[int]:
    ids: list[int] = []
    seen = set()
    for p in panels:
        for _, conds in (p.get("assays") or {}).items():
            for _, node in (conds or {}).items():
                for item in (node.get("runs") or []):
                    r = item.get("record")
                    if not r:
                        continue
                    rid = int(getattr(r, "id", 0) or 0)
                    if rid and rid not in seen:
                        seen.add(rid)
                        ids.append(rid)
    return ids


def _run_qc_summary_for_records(db: Session, record_ids: list[int], cols: dict) -> dict[int, dict]:
    """Return per-record QC rollups for measurement rows.

    Missing measurement_qc rows are treated as 'pending' (unreviewed).
    """
    if not record_ids or not cols:
        return {}

    from sqlalchemy import text as _text

    # Build IN clause with named params for sqlite.
    binds = []
    params = {}
    for i, rid in enumerate(record_ids):
        k = f"rid{i}"
        binds.append(f":{k}")
        params[k] = int(rid)

    q = _text(
        f"""
        SELECT dm.{cols['record_fk']} AS rid,
               SUM(CASE WHEN mq.status='approved' THEN 1 ELSE 0 END) AS approved,
               SUM(CASE WHEN mq.status='rejected' THEN 1 ELSE 0 END) AS rejected,
               SUM(CASE WHEN mq.status='quarantined' THEN 1 ELSE 0 END) AS quarantined,
               SUM(CASE WHEN mq.status IS NULL OR mq.status='unreviewed' THEN 1 ELSE 0 END) AS pending,
               COUNT(1) AS total
        FROM data_measurements dm
        LEFT JOIN measurement_qc mq ON mq.measurement_id = dm.id
        WHERE dm.{cols['record_fk']} IN ({', '.join(binds)})
        GROUP BY dm.{cols['record_fk']}
        """
    )
    rows = db.execute(q, params).mappings().all()
    out: dict[int, dict] = {}
    for r in rows:
        rid = int(r.get("rid") or 0)
        if not rid:
            continue
        out[rid] = {
            "approved": int(r.get("approved") or 0),
            "rejected": int(r.get("rejected") or 0),
            "quarantined": int(r.get("quarantined") or 0),
            "pending": int(r.get("pending") or 0),
            "total": int(r.get("total") or 0),
        }
    return out


def get_molecule_batch_ui_context(
    db: Session,
    molecule_id: int,
    *,
    selected_batch_id: int | None = None,
    qc_mode: str = "all",
) -> dict:
    """Return batch-first molecule context with QC-aware headline metrics and run-level QC badges."""
    from sqlalchemy import text as _text
    from psi.core.models import DataRecord

    qc_mode = (qc_mode or "all").strip().lower()
    if qc_mode not in ("all", "model_safe", "approved"):
        qc_mode = "all"

    base = get_molecule_experimental_context(db, molecule_id, selected_batch_id=selected_batch_id)

    panels = list(base.get("exp_batch_panels") or [])
    batches = list(base.get("exp_batches") or [])
    unassigned = list(base.get("exp_molecule_level_records") or [])

    cols = _reflect_measurement_cols(db)

    # Totals for Data Overview.
    total_records = db.query(DataRecord).filter(DataRecord.molecule_id == molecule_id).count()
    total_measurements = 0
    outlier_count = None
    if cols:
        try:
            total_measurements = int(
                db.execute(
                    _text(
                        f"""
                        SELECT COUNT(1) AS n
                        FROM data_measurements dm
                        JOIN data_records dr ON dm.{cols['record_fk']} = dr.id
                        WHERE dr.molecule_id = :mid
                        """
                    ),
                    {"mid": molecule_id},
                ).mappings().first()["n"]
            )
        except Exception:
            total_measurements = 0

        if cols.get("is_outlier") and cols.get("is_outlier") in cols.get("_all", set()):
            try:
                outlier_count = int(
                    db.execute(
                        _text(
                            f"""
                            SELECT COUNT(1) AS n
                            FROM data_measurements dm
                            JOIN data_records dr ON dm.{cols['record_fk']} = dr.id
                            WHERE dr.molecule_id = :mid AND dm.{cols['is_outlier']}=1
                            """
                        ),
                        {"mid": molecule_id},
                    ).mappings().first()["n"]
                )
            except Exception:
                outlier_count = None

    # Deterministic batch ordering.
    panels.sort(key=lambda p: _batch_sort_key(getattr(p.get("batch"), "batch_id", "")))
    batches.sort(key=lambda b: _batch_sort_key(getattr(b, "batch_id", "")))

    # Stabilize run ordering (ensures refresh determinism).
    for p in panels:
        for _, conds in (p.get("assays") or {}).items():
            for _, node in (conds or {}).items():
                runs = node.get("runs") or []
                runs.sort(
                    key=lambda item: (
                        0 if (item.get("record") and item["record"].run_date) else 1,
                        str(item.get("record").run_date or ""),
                        item.get("record").created_at if item.get("record") else 0,
                        int(getattr(item.get("record"), "id", 0)),
                    ),
                    reverse=True,
                )

    # Compute latest record ids for headline extraction.
    latest_by_panel: dict[int, int] = {}
    for idx, p in enumerate(panels):
        rid = _latest_record_id(p)
        if rid:
            latest_by_panel[idx] = int(rid)

    # Batch measurement counts in one query.
    meas_count_by_batch: dict[int, int] = {}
    if cols:
        try:
            rows = db.execute(
                _text(
                    f"""
                    SELECT dr.batch_id AS bid, COUNT(1) AS n
                    FROM data_measurements dm
                    JOIN data_records dr ON dm.{cols['record_fk']} = dr.id
                    WHERE dr.molecule_id = :mid AND dr.batch_id IS NOT NULL
                    GROUP BY dr.batch_id
                    """
                ),
                {"mid": molecule_id},
            ).mappings().all()
            for r in rows:
                bid = int(r.get("bid") or 0)
                if bid:
                    meas_count_by_batch[bid] = int(r.get("n") or 0)
        except Exception:
            meas_count_by_batch = {}

    # Run-level QC summaries (for small badges in tables).
    run_ids = _collect_record_ids_from_panels(panels)
    run_qc = _run_qc_summary_for_records(db, run_ids, cols)

    # Headline measurements and overview metric collection.
    batch_metric_values = {"purity": [], "kd": [], "titer": []}
    if cols:
        for idx, p in enumerate(panels):
            rid = latest_by_panel.get(idx)
            meas = _fetch_measurements_for_record(db, rid, cols, qc_mode=qc_mode) if rid else []
            headline_items = _headline_items_for_record(meas) if meas else []
            if not headline_items:
                headline_items = ["No measurements recorded"]
            p["headline_items"] = headline_items
            # attach per-batch measurement counts
            try:
                bid = int(getattr(p.get("batch"), "id", 0) or 0)
            except Exception:
                bid = 0
            p["measurement_count"] = meas_count_by_batch.get(bid) if bid else None

            purity = _best_measurement(meas, ["monomer_pct", "purity", "sec_purity", re.compile(r"\bmonomer\b")])
            kd = _best_measurement(meas, ["kd", "kd_nm", "kd_n", "affinity"])
            titer = _best_measurement(meas, ["titer", "expression", "yield", "concentration"])
            if purity and purity.get("value_num") is not None:
                batch_metric_values["purity"].append(float(purity["value_num"]))
            if kd and kd.get("value_num") is not None:
                batch_metric_values["kd"].append(float(kd["value_num"]))
            if titer and titer.get("value_num") is not None:
                batch_metric_values["titer"].append(float(titer["value_num"]))
    else:
        for p in panels:
            p.setdefault("headline_items", ["No measurements recorded"])
            p.setdefault("measurement_count", None)

    # Unassigned panel always last.
    if unassigned:
        unassigned.sort(
            key=lambda item: (
                0 if (item.get("record") and item["record"].run_date) else 1,
                str(item.get("record").run_date or ""),
                item.get("record").created_at if item.get("record") else 0,
                int(getattr(item.get("record"), "id", 0)),
            ),
            reverse=True,
        )
        panels.append(
            {
                "batch": None,
                "batch_label": "Unassigned",
                "assays": {},
                "glance": {},
                "record_count": len(unassigned),
                "unassigned_records": unassigned,
                "headline_items": ["No batch assigned"],
                "measurement_count": None,
                "details_key": "batch:__unassigned__",
            }
        )

    panels_non = [p for p in panels if p.get("batch") is not None]
    panels_un = [p for p in panels if p.get("batch") is None]
    panels = panels_non + panels_un

    def _mean(vals: list[float]) -> float | None:
        if not vals:
            return None
        try:
            return float(sum(vals) / len(vals))
        except Exception:
            return None

    data_overview = {
        "total_batches": len(batches) + (1 if unassigned else 0),
        "total_records": int(total_records),
        "total_measurements": int(total_measurements),
        "mean_purity": _mean(batch_metric_values["purity"]),
        "mean_kd": _mean(batch_metric_values["kd"]),
        "mean_titer": _mean(batch_metric_values["titer"]),
        "outlier_count": outlier_count,
    }

    return {
        "exp_batches": batches,
        "exp_batch_panels": panels,
        "exp_has_unassigned": bool(unassigned),
        "data_overview": data_overview,
        "exp_qc_mode": qc_mode,
        "exp_run_qc": run_qc,
    }
