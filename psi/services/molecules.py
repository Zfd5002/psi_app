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

    return {
        "molecule": m,
        "batches": batches,
        "data_records": data_records,
        "evidence": evidence,
        "file_links": file_links,
        "files_by_id": files_by_id,
        "audits": audits,
        "components": components,
        "domain_instances": domain_instances,
        "latest_run_events": run_events,
        "numbering_payload": numbering_payload,
        "feature_tracks": feature_tracks,
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
