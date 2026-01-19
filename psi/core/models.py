from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.utcnow()


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


class Molecule(Base):
    __tablename__ = "molecules"
    __table_args__ = (UniqueConstraint("program_id", "primary_id", name="uq_molecule_program_primary_id"),)

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)

    primary_id = Column(Text, nullable=False)
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
    evidence = relationship("Evidence", back_populates="molecule")

    components = relationship("MoleculeComponent", back_populates="molecule", cascade="all, delete-orphan")
    property_runs = relationship("PropertyRun", back_populates="molecule", cascade="all, delete-orphan")


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
    sha256 = Column(Text, nullable=False, unique=True)
    sequence_norm = Column(Text, nullable=False)
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

    run_date = Column(Text, nullable=True)  # ISO date string
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="data_records")
    molecule = relationship("Molecule", back_populates="data_records")
    batch = relationship("Batch", back_populates="data_records")

    citations = relationship("EvidenceCitation", back_populates="data_record", cascade="all, delete-orphan")


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
    created_at = Column(DateTime, default=utcnow, nullable=False)

    links = relationship("FileLink", back_populates="file", cascade="all, delete-orphan")


class FileLink(Base):
    __tablename__ = "file_links"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    entity_type = Column(Text, nullable=False)  # e.g., DataRecord
    entity_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    file = relationship("File", back_populates="links")


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


class DecisionSnapshot(Base):
    __tablename__ = "decision_snapshots"

    id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False)
    molecule_id = Column(Integer, ForeignKey("molecules.id"), nullable=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)

    decision_key = Column(Text, nullable=False)
    rules_version = Column(Text, nullable=False)
    inputs_json = Column(Text, nullable=False)
    outputs_json = Column(Text, nullable=False)
    evidence_ids_json = Column(Text, nullable=False)

    created_at = Column(DateTime, default=utcnow, nullable=False)

    program = relationship("Program", back_populates="decisions")
