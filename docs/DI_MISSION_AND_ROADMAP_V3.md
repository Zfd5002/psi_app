DI_MISSION_AND_ROADMAP_V3.md

PSI (Preclinical Systems Intelligence)
Decision Intelligence (DI) Governance Expansion — Version 3

Status: LOCKED
Effective Starting Version: 1.3.0
V3 Line Range: 1.3.0 → 1.3.9z###
Supersedes: DI_MISSION_AND_ROADMAP_v2.md

1. Purpose of V3

V3 expands PSI from a molecule-level deterministic decision engine into a structured, governance-grade, portfolio-operating system while preserving all invariants established in V1 and V2.

V3 introduces:

Molecule → Program → Portfolio abstraction

Attribution plumbing (single-machine foundation)

Deterministic program rollups

Governance-grade comparability surfaces

Policy-defined deterministic ranking

Deterministic Report Engine

Comparative reporting (2–5 entities)

Template ladder expansion

Lineage dashboards

Policy upgrade reproducibility hardening

V3 is expansion.
It is not refactoring.
It is not cleanup.

2. Invariants (Non-Negotiable)

The following invariants remain absolute:

Determinism: identical DB + identical policies + identical as-of ⇒ identical output

Snapshot immutability: no retroactive mutation

Replay sanctity: zero skips permitted

Policy-as-data: semantics encoded in versioned JSON catalogs

SQLite-only, local-first

No ML

No heuristic ranking

No adaptive scoring

No silent weights

Additive-only schema evolution

Heavy compute must be explicitly hash-safe

These invariants govern all V3 features.

3. Version Line Declaration

V3 begins at:

v1.3.0

All V3 patches exist in:

1.3.x → 1.3.9z###

This cleanly separates V3 from the 1.2.9x line and marks a new architectural expansion phase.

4. Core Architectural Expansion
4.1 Programs and Portfolios

Programs and Portfolios become first-class deterministic governance objects.

They:

Organize molecules

Enable rollups

Support ranking

Support comparative reporting

Provide lineage surfaces

They do not modify DI snapshot semantics.

All membership and ordering must be deterministic.

4.2 Attribution Plumbing

V3 introduces actor attribution fields for:

Program edits

Portfolio edits

Outcome labeling

Policy updates

Governance actions

Attribution is provenance metadata.

It is not scientific evidence.
It must not alter DI outputs.

4.3 Program Rollups

Program posture is deterministically derived from:

Molecule snapshots

Template outputs

Policy rules

No new scoring systems are introduced.

Rollups must cite:

Snapshot IDs

Policy versions

4.4 Governance-Grade Comparability

Comparability becomes an explicit governance object.

Categorical only:

Comparable

Conditionally Comparable

Not Comparable

Every determination must:

Cite rule invoked

Cite measurement keys

Cite snapshot IDs

No fuzzy comparability.

4.5 Deterministic Ranking

Ranking is permitted only if:

Entirely policy-defined

Fully explainable

Deterministic

Stable under tie-breaking

Every ranked entity must have:

Explicit reason trail

Policy version shown

Stable deterministic ordering

No composite scoring unless explicitly encoded in policy.

5. Deterministic Report Engine (V3.0f)

V3 introduces a formal report engine.

Reports are:

Deterministic

Policy-versioned

Snapshot-cited

Reproducible

Structured identically per type

Reports are regenerable artifacts.

Reports do not interpret beyond policy outputs.

6. Report Types (Authoritative List)

V3 formally defines four report types:

Program Report

Molecule Report

Program Comparative Report (2–5 programs)

Molecule Comparative Report (2–5 molecules)

No additional report types exist without governance amendment.

7. Program Report — Fixed Structure

All Program Reports share identical structure:

Metadata (as-of, policy versions, snapshot coverage)

Stage Determination

Molecule Overview Table

Cross-Molecule Comparability

Risk Landscape

Decision Lineage

Next-Best Experiments

Reproducibility Appendix

8. Molecule Report — Fixed Structure

All Molecule Reports share identical structure:

Identity + Context

Stage Determination

Confidence Decomposition

Mechanistic Evidence Map

Risk Profile

Experimental Gaps

Drift/History

Reproducibility Appendix

9. Program Comparative Report (2–5 Programs)

All Program Comparative Reports share identical structure:

Metadata

Stage Comparison Matrix

Ranking Surface (if enabled)

Cross-Program Comparability

Risk Landscape Comparison

Resource Implication Surface (policy-derived only)

Lineage Comparison

Reproducibility Appendix

Programs must be ordered deterministically.

10. Molecule Comparative Report (2–5 Molecules)

All Molecule Comparative Reports share identical structure:

Metadata

Stage Comparison Table

Confidence Component Comparison

Mechanistic Evidence Alignment Matrix

Risk Differential Analysis

Comparability Surface

Drift Comparison

Reproducibility Appendix

Molecules must be ordered deterministically.

11. Template Ladder Expansion

New templates may be introduced for additional development stages.

Existing template semantics must not change.

All new templates must:

Conform to snapshot contract

Pass replay regression

Be policy-versioned

12. Lineage Dashboards

V3 includes governance dashboards for:

Program lineage

Portfolio lineage

These surfaces must:

Be deterministic

Separate policy changes from evidence changes

Display attribution

13. Policy Upgrade Reproducibility Hardening

V3 formalizes policy upgrade governance:

Compatibility replay scaffolding

Delta reports for:

Ranking

Comparability

Template outputs

Explicit operator acknowledgment before semantic upgrades

14. Replay and Gate Requirements

All V3 patches must pass:

compileall

db_schema_sanity

di_contract_smoke

di_replay_regression --limit 5 (no skips)

pytest

No exceptions.

15. Non-Goals (Explicit)

V3 does not introduce:

ML ranking

Heuristic scoring

Adaptive thresholds

External services

Cloud dependencies

Postgres

Snapshot mutation

Nondeterministic behavior

16. Governance Status

This document is now the governing charter for PSI V3.

All V3 patches must:

Align with this roadmap

Respect invariants

Preserve replay integrity

Remain policy-defined

Amendments require explicit governance revision.
