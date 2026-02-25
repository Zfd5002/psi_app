PSI DI Mission & Roadmap v2
Version: 2.0 (Finalized)
Supersedes: DI_MISSION_AND_ROADMAP.md (v1)
Scope: Antibody and antibody–peptide fusion molecules
Date: 2026-02-25

I. Executive Framing
PSI DI v1 answered:
“Can we trust the engine?”
PSI DI v2 answers:
“Can scientists use PSI effortlessly to understand where a molecule stands, how trustworthy its data is, and what to do next — on modest hardware — without compromising deterministic governance?”
V2 prioritizes:
    • Scientist cognition
    • Clear molecule-level structural state
    • Clear evidence trust signals
    • Low-compute safety
    • Policy-as-data purity
    • Dependency-safe sequencing

II. Architectural Invariants (Non-Negotiable)
    1. Determinism
Same DB state + same policy + same as-of timestamp ⇒ identical output.
    2. Policy is Data
        ◦ Milestones, mappings, and risk logic must live in versioned JSON.
        ◦ No hidden milestone logic in Python.
        ◦ No hardcoded experiment–risk mappings long-term.
    3. Snapshot Immutability
Decision snapshots are content-hashed, replay-verifiable artifacts.
    4. Replay Stability
di_replay_regression must pass across upgrades.
    5. Low-Compute Safety
Heavy compute must be explicitly enabled. Default mode must be Surface Pro–safe.
    6. Scientist-First Default View
Governance detail must never obstruct interpretation.

III. Structural Themes

Theme A — Scientist-First Molecule Header
Every molecule page will display a persistent header containing:
    • Progress Bar (structural development advancement)
    • Confidence Bar (trustworthiness of current evidence)
These are independent signals.

A1. Progress Bar (Global Antibody Ladder)
All molecules follow a single antibody development pathway.
Progress is hybrid.

Early Milestones — Measurement Presence (Policy-Defined)
Defined in:
progress_policy_v0_1.json
Example structure:
{
  "early_milestones": {
    "expression_present": ["expr_yield_mgL"],
    "purification_present": ["purity_percent"],
    "basic_qc_present": ["aggregation_percent", "endotoxin_EU_mg"],
    "functional_assay_present": ["ec50_nM", "kd_nM"]
  },
  "di_milestones": {
    "scaleup_ready": "ready_for_scaleup_screen",
    "in_vivo_ready": "advance_to_in_vivo"
  }
}
These metric keys are policy-visible and versioned.
No milestone logic may live in Python.

Later Milestones — DI State
Unlocked only when corresponding DI templates pass under policy.
Template ordering enforcement is introduced in v2.0c (see Theme C).

Progress Bar Requirements (Sequencing Clarified)
    • Discrete stage ladder (not percentage-of-metrics).
    • Deterministic.
    • Fully explainable via hover text.
    • Based entirely on progress_policy_v0_1.json.
    • In v2.0b: structural ordering is not yet enforced; impossible ladder states are theoretically possible.
    • In v2.0c: impossible states are prevented via template prerequisite advisory.
This sequencing is intentional.

Theme B — Confidence Bar (Trust of Present Evidence Only)
Confidence reflects trustworthiness of currently available data.
It does not measure completeness.
Missing assays are neutral.

B1. Confidence Components
    1. QC Quality
    2. Reproducibility
    3. Comparability
    4. Interpretability (risk-flag-aware)
Each component may be:
    • Good
    • Concern
    • Not Assessed (neutral)

B2. Risk Flag Severity
Each risk flag in policy must include:
{
  "severity": "high" | "medium" | "low"
}
Interpretability must render severity tiers distinctly.
No implicit weighting allowed.

B3. Confidence Scalar Rule (Strict Constraint)
A summary scalar is optional but must:
    • Be directly derivable from visible component states.
    • Use only counting or threshold logic.
    • Not use weighted averages.
    • Not use hidden weights.
    • Be reproducible by a scientist without calculation beyond counting.
Allowed:
    • ≥1 high-severity concern ⇒ Amber
    • ≥2 medium concerns ⇒ Amber
Disallowed:
    • Weighted formulas
    • Composite scoring models
The scalar must never obscure component-level truth.

Theme C — Structural Integrity Enforcement

C1. Template Prerequisite Advisory (v2.0c)
Templates must respect ordering.
Example:
    • Cannot run advance_to_in_vivo unless ready_for_scaleup_screen exists and passed.
Enforcement must:
    • Be deterministic
    • Prevent incoherent progress states
    • Surface advisory in UI
    • Not require sub-assessment abstraction yet
Note:
v2.0c may temporarily query DI snapshot states directly.
Sub-assessment consolidation occurs in v2.0e.

C2. Risk Severity Integration
Risk severity tiers are introduced in v2.0c and required for confidence bar logic.

Theme D — Governance Hardening (Carryover from v1)

D1. soe.py Refactor (A1)
Eliminate duplication across:
    • build_soe_v0_2
    • build_soe_v0_3
    • molecule-specific variants
Shared internal builders.
No schema change.
Replay parity required.

D2. Error Output Builder (A3)
Replace ad-hoc error-output construction.
Guarantee:
    • All happy-path top-level fields present in error outputs.
    • Contract tests assert parity.

D3. Catalog-Driven Risk Mapping (A2)
Replace hardcoded _RISK_FLAG_TO_EXPERIMENT_KEYS.
Experiment catalog entries gain:
{
  "resolves_risk_flags": []
}
NBE derives mapping exclusively from catalog.

D4. Sub-Assessment Library (A4)
Extract reusable sub-assessments:
    • Material readiness
    • Reproducibility signal
    • Comparability summary
    • Mechanism readiness
Refactors temporary logic introduced in v2.0c.

D5. Value Function Enforcement Reason (A5)
Add explicit field:
value_functions_enforcement_reason
Possible values:
    • active
    • policy_flag_off
    • evaluator_version_mismatch
    • not_applicable
Must surface in UI.

Theme E — Heavy Compute Mode
Environment variable:
PSI_HEAVY_COMPUTE=0  (default)
PSI_HEAVY_COMPUTE=1  (future workstation)
When OFF:
    • GPU-backed producers disabled
    • Expensive background jobs suppressed
    • DI outputs unaffected
    • UI clearly states heavy compute disabled
When ON:
    • Advanced compute producers allowed
    • Must not affect DI snapshot hash
    • Non-deterministic compute excluded from hash
V2 introduces scaffolding only. No GPU producers in V2.

Theme F — Closed-Loop Outcome Dataset (v2.1)
To enable meaningful time-to-outcome analysis:
Add additive field:
OutcomeLabel.outcome_event_date: datetime
This does not affect DI hash or replay.

OutcomeDataset Structure
OutcomeDataset
- snapshot_id
- policy_semantics_hash
- evidence_fingerprint
- decision_state
- outcome_label
- di_review_verdict
- outcome_event_date
- days_to_outcome (derived)
Rules:
    • days_to_outcome = outcome_event_date - snapshot_created_at
    • If outcome_event_date is null, days_to_outcome omitted
    • Outcome metadata must not influence DI outputs

IV. Phased Implementation Plan

v2.0a — Infrastructure First
    • D1 SoE refactor
    • D2 error builder consolidation
    • Define progress_policy_v0_1.json
    • Contract tests
    • Replay regression clean

v2.0b — Scientist UI Foundation
    • Molecule header scaffold
    • Scientist/Governance toggle
    • Drift plain-English translation
    • Progress bar rendering
    • Heavy Compute scaffold
Note:
Ordering enforcement not yet active.

v2.0c — Structural Coherence
    • Template prerequisite advisory
    • Add risk flag severity tiers
    • Minimal UI wiring for severity

v2.0d — Confidence Bar
    • Component-based rendering
    • Severity-aware interpretability
    • Non-weighted scalar logic

v2.0e — Policy Consolidation
    • Catalog-driven risk mapping
    • Sub-assessment library extraction
    • Enforcement reason surfacing

v2.1 — Outcome Dataset Export
    • Add outcome_event_date
    • Implement OutcomeDataset export
    • Ensure additive-only schema migration
    • Replay regression clean

V3+
    • Multi-user sync
    • Identity plumbing
    • Multi-batch ranking
    • Additional templates
    • GPU-backed compute producers

V. Definition of Success
By end of V2:
    • Every molecule page communicates stage and trust clearly.
    • Progress ladder is policy-driven.
    • Impossible states eliminated (post v2.0c).
    • Confidence never penalizes missing assays.
    • No weighted heuristics exist.
    • Heavy compute safe by default.
    • Risk mappings are catalog-driven.
    • SoE duplication eliminated.
    • Error builder hardened.
    • Outcome dataset export exists.
    • Replay regression passes.

VI. Drift Guard Checklist
Before merging any feature:
    1. Does it preserve determinism?
    2. Does it preserve replay stability?
    3. Does it run safely with heavy compute OFF?
    4. Is logic policy-visible?
    5. Is missing evidence neutral?
    6. Is any scalar derivable from visible components?
    7. Does it avoid increasing maintenance burden?
If any answer is “no,” redesign.

Final Position
V1 made the engine trustworthy.
V2 makes it intuitive, coherent, policy-grounded, and safe on modest hardware — without sacrificing deterministic governance.
This document is internally consistent, dependency-aware, polarity-corrected, and ready for execution.

