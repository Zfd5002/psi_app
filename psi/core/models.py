from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, Float, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    molecules = relationship("Molecule", back_populates="program", cascade="all, delete-orphan")
    data_records = relationship("DataRecord", back_populates="program", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="program", cascade="all, delete-orphan")
    decisions = relationship("DecisionSnapshot", back_populates="program", cascade="all, delete-orphan")
    experiment_tasks = relationship("ExperimentTask", back_populates="program", cascade="all, delete-orphan")
    memberships = relationship("ProgramMembership", back_populates="program", cascade="all, delete-orphan")
    molecule_statuses = relationship("ProgramMoleculeStatus", back_populates="program", cascade="all, delete-orphan")
    portfolio_memberships = relationship("PortfolioMembership", back_populates="program", cascade="all, delete-orphan")
    scientific_claims = relationship("ScientificClaim", back_populates="program", cascade="all, delete-orphan")


class Molecule(Base):
    __tablename__ = "molecules"
    __table_args__ = (UniqueConstraint("program_id", "primary_id", name="uq_molecule_program_primary_id"),)

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)

    primary_id = Column(Text, nullable=False)
    composition_sha256 = Column(Text, nullable=True)  # v1.2.0: canonical HC/LC role→chain hash

    title = Column(Text, nullable=True)
    # Legacy user-provided description. Remains for backward compatibility.
    description = Column(Text, nullable=True)

    # v1.01: antibody-aware modeling
    molecule_format = Column(Text, nullable=True)  # IgG | scFv | NULL (legacy/unstructured)
    description_auto = Column(Text, nullable=True)
    description_user = Column(Text, nullable=True)
    heavy_compute_enabled = Column(Integer, nullable=False, default=0)  # 0/1, persisted user intent

    # Legacy sequence blob. Must remain populated for backward compatibility.
    sequences = Column(Text, nullable=True)  # FASTA/JSON/etc

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="molecules")
    batches = relationship("Batch", back_populates="molecule", cascade="all, delete-orphan")
    data_records = relationship("DataRecord", back_populates="molecule")
    experiment_tasks = relationship("ExperimentTask", back_populates="molecule", cascade="all, delete-orphan")
    evidence = relationship("Evidence", back_populates="molecule")

    components = relationship("MoleculeComponent", back_populates="molecule", cascade="all, delete-orphan")
    property_runs = relationship("PropertyRun", back_populates="molecule", cascade="all, delete-orphan")
    program_memberships = relationship("ProgramMembership", back_populates="molecule", cascade="all, delete-orphan")
    program_statuses = relationship("ProgramMoleculeStatus", back_populates="molecule", cascade="all, delete-orphan")
    derivations_as_parent = relationship(
        "MoleculeDerivation",
        foreign_keys="MoleculeDerivation.parent_molecule_id",
        back_populates="parent_molecule",
        cascade="all, delete-orphan",
    )
    derivations_as_child = relationship(
        "MoleculeDerivation",
        foreign_keys="MoleculeDerivation.child_molecule_id",
        back_populates="child_molecule",
        cascade="all, delete-orphan",
    )
    variant_set_memberships = relationship("BuilderVariantSetMember", back_populates="molecule", cascade="all, delete-orphan")
    scientific_claims = relationship("ScientificClaim", back_populates="molecule", cascade="all, delete-orphan")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    memberships = relationship("PortfolioMembership", back_populates="portfolio", cascade="all, delete-orphan")


class ProgramMembership(Base):
    __tablename__ = "program_membership"
    __table_args__ = (
        UniqueConstraint("program_id", "molecule_id", name="uq_program_membership_program_molecule"),
    )

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)
    sort_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="memberships")
    molecule = relationship("Molecule", back_populates="program_memberships")


class ProgramMoleculeStatus(Base):
    __tablename__ = "program_molecule_status"
    __table_args__ = (
        UniqueConstraint("program_id", "molecule_id", name="uq_program_molecule_status_program_molecule"),
    )

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False, index=True)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False, index=True)
    role = Column(Text, nullable=False, default="active")
    rationale = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=utcnow, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="molecule_statuses")
    molecule = relationship("Molecule", back_populates="program_statuses")


class MoleculeDerivation(Base):
    __tablename__ = "molecule_derivations"

    id = Column(Integer, primary_key=True)
    parent_molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False, index=True)
    child_molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False, index=True)
    derivation_type = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    edit_payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    parent_molecule = relationship("Molecule", foreign_keys=[parent_molecule_id], back_populates="derivations_as_parent")
    child_molecule = relationship("Molecule", foreign_keys=[child_molecule_id], back_populates="derivations_as_child")


class BuilderVariantSet(Base):
    __tablename__ = "builder_variant_sets"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    builder_mode = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)
    spec_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    members = relationship("BuilderVariantSetMember", back_populates="variant_set", cascade="all, delete-orphan")


class BuilderVariantSetMember(Base):
    __tablename__ = "builder_variant_set_members"
    __table_args__ = (
        UniqueConstraint("variant_set_id", "sort_index", name="uq_builder_variant_set_member_sort"),
        Index("ix_builder_variant_set_member_variant_set_id", "variant_set_id"),
        Index("ix_builder_variant_set_member_molecule_id", "molecule_id"),
    )

    id = Column(Integer, primary_key=True)
    variant_set_id = Column(Integer, ForeignKey("builder_variant_sets.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)
    sort_index = Column(Integer, nullable=False, default=0)
    member_label = Column(Text, nullable=False)
    member_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    variant_set = relationship("BuilderVariantSet", back_populates="members")
    molecule = relationship("Molecule", back_populates="variant_set_memberships")


class PortfolioMembership(Base):
    __tablename__ = "portfolio_membership"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "program_id", name="uq_portfolio_membership_portfolio_program"),
    )

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    sort_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    portfolio = relationship("Portfolio", back_populates="memberships")
    program = relationship("Program", back_populates="portfolio_memberships")


class MoleculeComponent(Base):
    __tablename__ = "molecule_components"
    __table_args__ = (
        UniqueConstraint("molecule_id", "role", name="uq_molecule_component_role"),
    )

    id = Column(Integer, primary_key=True)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)

    # HC1, HC2, LC1, LC2, VH, VL, linker, fusion
    role = Column(Text, nullable=False)
    fasta = Column(Text, nullable=False)
    sha256 = Column(Text, nullable=False)

    # vNext: canonical sequence registry link (additive)
    sequence_entity_id = Column(Integer, ForeignKey("sequence_entities.id"), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    molecule = relationship("Molecule", back_populates="components")
    sequence_entity = relationship("SequenceEntity")


class SequenceEntity(Base):
    """Global canonical sequence registry.

    Used for dedupe, search, and domain-level artifact caching.
    """

    __tablename__ = "sequence_entities"

    id = Column(Integer, primary_key=True)
    chain_id = Column(Text, nullable=True, unique=True)  # v1.2.0: CHAINXXX
    sha256 = Column(Text, nullable=False, unique=True)
    sequence_norm = Column(Text, nullable=False)
    type_hint = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    length = Column(Integer, nullable=False)
    alphabet = Column(Text, nullable=False, default="AA")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class DomainInstance(Base):
    """A labeled span on a molecule component.

    Indexing convention (vNext): 0-based, half-open [start_idx, end_idx).
    """

    __tablename__ = "domain_instances"

    id = Column(Integer, primary_key=True)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)
    component_id = Column(Integer, ForeignKey("molecule_components.id"), nullable=False)

    domain_type = Column(Text, nullable=False)  # VH, VL, CH1, PD-L1_IgV, etc.
    start_idx = Column(Integer, nullable=False)
    end_idx = Column(Integer, nullable=False)

    domain_sequence_id = Column(Integer, ForeignKey("sequence_entities.id"), nullable=True)

    source = Column(Text, nullable=False, default="auto")  # auto|user
    method = Column(Text, nullable=True)  # anarci/abnumber/rule_based/manual_span
    tool_name = Column(Text, nullable=True)
    tool_version = Column(Text, nullable=True)
    settings_hash = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="success")  # success|failure
    warnings_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    molecule = relationship("Molecule")
    component = relationship("MoleculeComponent")
    domain_sequence = relationship("SequenceEntity")


class DomainArtifact(Base):
    """Cacheable computed artifact keyed by canonical sequence + tool/version/settings."""

    __tablename__ = "domain_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "sequence_id",
            "artifact_type",
            "domain_type",
            "tool_name",
            "tool_version",
            "settings_hash",
            name="uq_domain_artifact_key",
        ),
    )

    id = Column(Integer, primary_key=True)
    sequence_id = Column(Integer, ForeignKey("sequence_entities.id"), nullable=False)
    artifact_type = Column(Text, nullable=False)  # ab_numbering, liability_sites, etc.
    domain_type = Column(Text, nullable=True)  # VH/VL/etc when relevant

    tool_name = Column(Text, nullable=False)
    tool_version = Column(Text, nullable=False)
    settings_hash = Column(Text, nullable=False)

    status = Column(Text, nullable=False, default="running")  # running|success|failure
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    sequence = relationship("SequenceEntity")


class PropertyRunEvent(Base):
    """Append-only event log for computed runs."""

    __tablename__ = "property_run_events"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("property_runs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    step = Column(Text, nullable=False)
    level = Column(Text, nullable=False, default="info")  # info|warn|error
    message = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=True)

    run = relationship("PropertyRun")


class PropertyRun(Base):
    __tablename__ = "property_runs"

    id = Column(Integer, primary_key=True)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)

    input_hash = Column(Text, nullable=False)
    trigger_reason = Column(Text, nullable=False)
    compute_tier = Column(Text, nullable=False)  # FAST | FAST+HEAVY
    status = Column(Text, nullable=False, default="running")  # running|success|failure
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    molecule = relationship("Molecule", back_populates="property_runs")
    values = relationship("PropertyValue", back_populates="run", cascade="all, delete-orphan")


class PropertyValue(Base):
    __tablename__ = "property_values"
    __table_args__ = (
        UniqueConstraint("run_id", "property_key", name="uq_property_value_run_key"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("property_runs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)

    property_key = Column(Text, nullable=False)
    label = Column(Text, nullable=False)
    value_json = Column(Text, nullable=True)
    tier = Column(Text, nullable=False)  # FAST | HEAVY

    created_at = Column(DateTime, default=utcnow, nullable=False)

    run = relationship("PropertyRun", back_populates="values")


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("molecule_id", "batch_id", name="uq_batch_molecule_batch_id"),)

    id = Column(Integer, primary_key=True)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)

    batch_id = Column(Text, nullable=False)  # e.g., TCB-001-001
    title = Column(Text, nullable=True)
    expression_notes = Column(Text, nullable=True)
    purification_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    molecule = relationship("Molecule", back_populates="batches")
    data_records = relationship("DataRecord", back_populates="batch")
    evidence = relationship("Evidence", back_populates="batch")


class DataRecord(Base):
    __tablename__ = "data_records"

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)

    domain = Column(Text, nullable=False)
    data_type = Column(Text, nullable=False)
    method = Column(Text, nullable=False)

    title = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)

    params_json = Column(Text, nullable=True)
    results_json = Column(Text, nullable=True)

    # v1.2.0: Experiment v2 (batch-centric)
    primary_result_text = Column(Text, nullable=True)
    raw_inputs_json = Column(Text, nullable=True)
    derived_outputs_json = Column(Text, nullable=True)
    is_included = Column(Integer, nullable=False, default=1)
    excluded_reason = Column(Text, nullable=True)

    run_date = Column(Text, nullable=True)  # ISO date string
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="data_records")
    molecule = relationship("Molecule", back_populates="data_records")
    batch = relationship("Batch", back_populates="data_records")

    citations = relationship("EvidenceCitation", back_populates="data_record", cascade="all, delete-orphan")
    linked_experiment_tasks = relationship("ExperimentTask", back_populates="linked_data_record")
    scientific_claim_links = relationship("ScientificClaimEvidenceLink", back_populates="data_record", cascade="all, delete-orphan")


class ExperimentTask(Base):
    __tablename__ = "program_experiment_tasks"
    __table_args__ = (
        Index("ix_experiment_tasks_program_status", "program_id", "status"),
        Index("ix_experiment_tasks_molecule_status", "molecule_id", "status"),
        Index("ix_experiment_tasks_program_molecule", "program_id", "molecule_id"),
        Index("ix_experiment_tasks_source_snapshot_id", "source_snapshot_id"),
        Index("ix_experiment_tasks_linked_data_record_id", "linked_data_record_id"),
    )

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=False)
    metric_key = Column(Text, nullable=True)
    suggested_assay = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="planned")
    owner_text = Column(Text, nullable=True)
    due_date = Column(Text, nullable=True)  # ISO date string
    urgency = Column(Text, nullable=False, default="normal")
    source_kind = Column(Text, nullable=False, default="manual")
    source_snapshot_id = Column(Integer, ForeignKey("decision_snapshots.id"), nullable=True)
    linked_data_record_id = Column(Integer, ForeignKey("data_records.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="experiment_tasks")
    molecule = relationship("Molecule", back_populates="experiment_tasks")
    source_snapshot = relationship("DecisionSnapshot", back_populates="experiment_tasks")
    linked_data_record = relationship("DataRecord", back_populates="linked_experiment_tasks")
    scientific_claim_links = relationship("ScientificClaimTaskLink", back_populates="experiment_task", cascade="all, delete-orphan")


class ScientificClaim(Base):
    __tablename__ = "scientific_claims"
    __table_args__ = (
        Index("ix_scientific_claims_scope_status", "scope_type", "status"),
        Index("ix_scientific_claims_molecule_status", "molecule_id", "status"),
        Index("ix_scientific_claims_program_status", "program_id", "status"),
        Index("ix_scientific_claims_type_status", "claim_type", "status"),
    )

    id = Column(Integer, primary_key=True)
    scope_type = Column(Text, nullable=False, default="molecule")
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    title = Column(Text, nullable=False)
    claim_type = Column(Text, nullable=False)
    statement = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="hypothesis")
    confidence_level = Column(Text, nullable=False, default="low")
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    molecule = relationship("Molecule", back_populates="scientific_claims")
    program = relationship("Program", back_populates="scientific_claims")
    evidence_links = relationship("ScientificClaimEvidenceLink", back_populates="claim", cascade="all, delete-orphan")
    decision_links = relationship("ScientificClaimDecisionLink", back_populates="claim", cascade="all, delete-orphan")
    task_links = relationship("ScientificClaimTaskLink", back_populates="claim", cascade="all, delete-orphan")


class ScientificClaimEvidenceLink(Base):
    __tablename__ = "scientific_claim_evidence_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "data_record_id", "direction", name="uq_claim_evidence_direction"),
        Index("ix_claim_evidence_claim", "claim_id"),
        Index("ix_claim_evidence_record", "data_record_id"),
    )

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("scientific_claims.id"), nullable=False)
    data_record_id = Column(Integer, ForeignKey("data_records.id"), nullable=False)
    direction = Column(Text, nullable=False, default="contextual")
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    claim = relationship("ScientificClaim", back_populates="evidence_links")
    data_record = relationship("DataRecord", back_populates="scientific_claim_links")


class ScientificClaimDecisionLink(Base):
    __tablename__ = "scientific_claim_decision_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "decision_snapshot_id", "relationship_type", name="uq_claim_decision_rel"),
        Index("ix_claim_decision_claim", "claim_id"),
        Index("ix_claim_decision_snapshot", "decision_snapshot_id"),
    )

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("scientific_claims.id"), nullable=False)
    decision_snapshot_id = Column(Integer, ForeignKey("decision_snapshots.id"), nullable=False)
    relationship_type = Column(Text, nullable=False, default="informs")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    claim = relationship("ScientificClaim", back_populates="decision_links")
    decision_snapshot = relationship("DecisionSnapshot")


class ScientificClaimTaskLink(Base):
    __tablename__ = "scientific_claim_task_links"
    __table_args__ = (
        UniqueConstraint("claim_id", "experiment_task_id", "relationship_type", name="uq_claim_task_rel"),
        Index("ix_claim_task_claim", "claim_id"),
        Index("ix_claim_task_task", "experiment_task_id"),
    )

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("scientific_claims.id"), nullable=False)
    experiment_task_id = Column(Integer, ForeignKey("program_experiment_tasks.id"), nullable=False)
    relationship_type = Column(Text, nullable=False, default="tests")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    claim = relationship("ScientificClaim", back_populates="task_links")
    experiment_task = relationship("ExperimentTask", back_populates="scientific_claim_links")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)

    domain = Column(Text, nullable=False)
    evidence_type = Column(Text, nullable=False)
    strength = Column(Integer, nullable=False, default=0)

    summary = Column(Text, nullable=False)
    details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="evidence")
    molecule = relationship("Molecule", back_populates="evidence")
    batch = relationship("Batch", back_populates="evidence")

    citations = relationship("EvidenceCitation", back_populates="evidence", cascade="all, delete-orphan")


class EvidenceCitation(Base):
    __tablename__ = "evidence_citations"
    __table_args__ = (UniqueConstraint("evidence_id", "data_record_id", name="uq_evidence_data_unique"),)

    id = Column(Integer, primary_key=True)
    evidence_id = Column(Integer, ForeignKey("evidence.id"), nullable=False)
    data_record_id = Column(Integer, ForeignKey("data_records.id"), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    evidence = relationship("Evidence", back_populates="citations")
    data_record = relationship("DataRecord", back_populates="citations")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    stored_name = Column(Text, nullable=False, unique=True)
    original_name = Column(Text, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    mime = Column(Text, nullable=True)
    sha256 = Column(Text, nullable=False)

    # v1.2.6: provenance foundation (all optional, additive)
    source_kind = Column(Text, nullable=True)   # upload | import_path | generated
    source_path = Column(Text, nullable=True)   # original location if imported
    collected_at = Column(DateTime, nullable=True)
    imported_at = Column(DateTime, nullable=True)
    instrument = Column(Text, nullable=True)
    operator = Column(Text, nullable=True)
    run_id = Column(Text, nullable=True)
    tags_json = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    links = relationship("FileLink", back_populates="file", cascade="all, delete-orphan")


class FileLink(Base):
    __tablename__ = "file_links"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    entity_type = Column(Text, nullable=False)  # e.g., DataRecord
    entity_id = Column(Integer, nullable=False)

    # v1.2.6: typed linkage
    role = Column(Text, nullable=True)  # raw_input | processed_output | report | plot | protocol | other
    label = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    file = relationship("File", back_populates="links")


class FileDerivation(Base):
    __tablename__ = "file_derivations"

    id = Column(Integer, primary_key=True)
    parent_file_id = Column(Integer, nullable=False, index=True)
    child_file_id = Column(Integer, nullable=False, index=True)
    transform = Column(Text, nullable=True)
    tool_name = Column(Text, nullable=True)
    tool_version = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
class MeasurementQCEvent(Base):
    """Append-only QC event log for extracted measurements.

    This is the source of truth for review/audit history. Do not UPDATE rows;
    always INSERT new events.
    """

    __tablename__ = "measurement_qc_events"

    id = Column(Integer, primary_key=True)

    # data_measurements.id (managed outside ORM). Intentionally no FK.
    measurement_id = Column(Integer, nullable=False, index=True)

    # Optional convenience linkage for UI grouping.
    record_id = Column(Integer, ForeignKey("data_records.id"), nullable=True, index=True)

    # Optional: when targeting a conceptual metric rather than a specific row.
    metric_key = Column(Text, nullable=True)

    action = Column(Text, nullable=False)  # approve/reject/quarantine/clear/note
    status_after = Column(Text, nullable=False)  # approved/rejected/quarantined/unreviewed

    actor = Column(Text, nullable=False)
    note = Column(Text, nullable=True)

    # Model-safety policy metadata
    ignore_policy = Column(Text, nullable=True)  # include/exclude_soft/exclude_hard/quarantine
    ignore_reason_code = Column(Text, nullable=True)
    ignore_note = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    record = relationship("DataRecord", lazy="joined")


class MeasurementQC(Base):
    """Latest-state cache for measurement QC.

    This table may be UPDATED (it's derived). Governance truth remains in
    MeasurementQCEvent.
    """

    __tablename__ = "measurement_qc"
    __table_args__ = (UniqueConstraint("measurement_id", name="uq_measurement_qc_measurement_id"),)

    id = Column(Integer, primary_key=True)

    # data_measurements.id (managed outside ORM). Intentionally no FK.
    measurement_id = Column(Integer, nullable=False, index=True)

    # Optional convenience linkage for UI grouping.
    record_id = Column(Integer, ForeignKey("data_records.id"), nullable=True, index=True)

    metric_key = Column(Text, nullable=True)

    status = Column(Text, nullable=False, default="unreviewed")  # unreviewed/approved/rejected/quarantined

    ignore_policy = Column(Text, nullable=False, default="include")  # include/exclude_soft/exclude_hard/quarantine
    ignore_reason_code = Column(Text, nullable=True)
    ignore_note = Column(Text, nullable=True)

    last_event_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    record = relationship("DataRecord", lazy="joined")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    action = Column(Text, nullable=False)  # create/update/delete/link/unlink
    timestamp = Column(DateTime, default=utcnow, nullable=False)
    actor = Column(Text, nullable=False, default="local-user")
    before_json = Column(Text, nullable=True)
    after_json = Column(Text, nullable=True)
    diff_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)


class Actor(Base):
    __tablename__ = "actors"

    id = Column(Integer, primary_key=True)
    display_name = Column(Text, nullable=False)
    handle = Column(Text, nullable=False, unique=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class AttributionEvent(Base):
    __tablename__ = "attribution_events"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("actors.id"), nullable=False)
    event_type = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    actor_rel = relationship("Actor")


class ProgramRollup(Base):
    __tablename__ = "program_rollups"

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    as_of = Column(DateTime, nullable=False)
    policy_pin = Column(Text, nullable=False)
    policy_package_hash = Column(Text, nullable=True)
    snapshot_ids_json = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program")


class ComparabilityAssessment(Base):
    __tablename__ = "comparability_assessments"

    id = Column(Integer, primary_key=True)
    left_scope_type = Column(Text, nullable=False)   # molecule|program
    left_scope_id = Column(Integer, nullable=False)
    right_scope_type = Column(Text, nullable=False)  # molecule|program
    right_scope_id = Column(Integer, nullable=False)
    status = Column(Text, nullable=False)  # comparable|conditionally_comparable|not_comparable
    rule_id = Column(Text, nullable=False)
    cited_measurement_keys_json = Column(Text, nullable=False)
    cited_snapshot_ids_json = Column(Text, nullable=False)
    as_of = Column(DateTime, nullable=False)
    policy_id = Column(Text, nullable=False)
    policy_version = Column(Text, nullable=False)
    policy_package_hash = Column(Text, nullable=True)
    policy_semantics_hash = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class ReportRun(Base):
    __tablename__ = "report_runs"

    id = Column(Integer, primary_key=True)
    report_type = Column(Text, nullable=False)
    subject_ids_json = Column(Text, nullable=False)
    as_of = Column(DateTime, nullable=False)
    policy_pins_json = Column(Text, nullable=False)
    snapshot_coverage_json = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class DIRun(Base):
    __tablename__ = "di_runs"
    __table_args__ = (UniqueConstraint("run_id", name="uq_di_runs_run_id"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Text, nullable=False)
    decision_key = Column(Text, nullable=False)
    as_of = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    producer_id = Column(Text, nullable=False, default="di.rules")
    producer_version = Column(Text, nullable=False, default="v1")
    policy_pins_json = Column(Text, nullable=False)
    policy_semantics_hash = Column(Text, nullable=True)
    policy_package_hash = Column(Text, nullable=True)
    catalog_ref_json = Column(Text, nullable=True)
    scope_root_type = Column(Text, nullable=False, default="molecule")
    scope_root_id = Column(Integer, nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)

    program = relationship("Program")
    subjects = relationship("DIRunSubject", back_populates="di_run", cascade="all, delete-orphan")


class DIRunSubject(Base):
    __tablename__ = "di_run_subjects"
    __table_args__ = (
        UniqueConstraint("di_run_id", "subject_index", name="uq_di_run_subjects_run_subject_index"),
        Index("ix_di_run_subjects_scope_compound", "molecule_id", "batch_id", "scope_type"),
    )

    id = Column(Integer, primary_key=True)
    di_run_id = Column(Integer, ForeignKey("di_runs.id"), nullable=False, index=True)
    subject_index = Column(Integer, nullable=False)
    scope_type = Column(Text, nullable=False)
    scope_id = Column(Integer, nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=True, index=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True, index=True)
    decision_snapshot_id = Column(Integer, ForeignKey("decision_snapshots.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    di_run = relationship("DIRun", back_populates="subjects")
    molecule = relationship("Molecule")
    batch = relationship("Batch")
    decision_snapshot = relationship("DecisionSnapshot")


class PolicyUpgradeSession(Base):
    __tablename__ = "policy_upgrade_sessions"

    id = Column(Integer, primary_key=True)
    old_policy_pins_json = Column(Text, nullable=False)
    new_policy_pins_json = Column(Text, nullable=False)
    delta_payload_json = Column(Text, nullable=False)
    operator_acknowledged = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)


class DecisionSnapshot(Base):
    __tablename__ = "decision_snapshots"

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)

    decision_key = Column(Text, nullable=False)
    rules_version = Column(Text, nullable=False)

    # v1.2.9b: schema discrimination + provenance for DI snapshots.
    # Additive, nullable to preserve older DBs and legacy snapshots.
    engine_key = Column(Text, nullable=True)        # e.g. "di" vs NULL for legacy rules engine
    schema_version = Column(Text, nullable=True)    # e.g. "di.snapshot.v0_1"

    inputs_json = Column(Text, nullable=False)
    outputs_json = Column(Text, nullable=False)
    evidence_ids_json = Column(Text, nullable=False)

    as_of_ts = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # v1.2.9q: snapshot lifecycle governance (additive).
    # These fields do NOT affect snapshot immutability: they are metadata that clarifies lifecycle.
    is_superseded = Column(Integer, nullable=True)          # 0/1; NULL allowed for older rows
    superseded_by_snapshot_id = Column(Integer, ForeignKey("decision_snapshots.id"), nullable=True)
    superseded_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="decisions")
    experiment_tasks = relationship("ExperimentTask", back_populates="source_snapshot")
    outcomes = relationship("OutcomeLabel", back_populates="snapshot", cascade="all, delete-orphan")

class OutcomeLabel(Base):
    __tablename__ = "outcome_labels"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("decision_snapshots.id"), nullable=False, index=True)

    name = Column(Text, nullable=False, index=True)
    value_text = Column(Text, nullable=True)
    value_num = Column(Float, nullable=True)
    value_bool = Column(Integer, nullable=True)
    outcome_event_date = Column(DateTime, nullable=True)

    version = Column(Text, default="v1", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    snapshot = relationship("DecisionSnapshot", back_populates="outcomes")
