# DI Mission & Roadmap (Markdown mirror)

> Source: DI_MISSION_AND_ROADMAP.docx (committed)

Below is a living checklist / roadmap you can paste into a Word doc and keep bringing back. It’s intentionally versioned, goal-driven, and drift-resistant. It describes an elite DI system as the end state, while keeping early iterations focused and achievable on your current hardware.

## PSI Decision Intelligence (DI) Mission & Roadmap

## Mission statement

PSI Decision Intelligence (DI) exists to help scientists and biotech teams make better, faster, more reproducible decisions by turning PSI’s measured data into explainable, deterministic, policy-versioned decision outputs that:

Summarize the State of Evidence (what we know, how reliable it is, what was ignored and why)

Assess Decision Readiness for specific decision contexts (e.g., “advance to in vivo”)

Surface risks and uncertainties (including non-monotonic biology such as internalization-sensitive binding)

## Recommend Next Best Experiments with transparent rationale

Enable controlled ranking/shortlisting only when warranted by evidence completeness and policy

DI must never silently mutate source data, never hide logic in opaque weights, and must always produce outputs that are exportable, auditable, and reproducible.

## Architectural principles (non-negotiable)

Determinism first
Same PSI DB state + same DI policy version + same as-of timestamp ⇒ same DI output.

Explainability is a first-class output
DI outputs must include: triggered rules, failed gates, evidence used, evidence ignored, and rationale.

Policy is data
Decision logic must be versioned, hashable, and exportable. “Code paths” cannot be the only source of truth.

No implicit biological assumptions
Metrics may be non-monotonic (e.g., binding), context-dependent, and assay-dependent. DI must encode these explicitly.

Human remains the decider
DI suggests, explains, and structures; it does not auto-approve/auto-reject or change QC state.

## PSI architecture context (how DI fits PSI)

PSI already has the right substrate:

## Canonical measurement registry (measurement keys + conversions)

## Measurement table with provenance (producer, version, run_id, timestamps)

## QC system (append-only events + latest-state cache, ignore policy)

Deterministic exporter (stable selection rules, stable ordering, as-of capability)

## DecisionSnapshot / OutcomeLabel models (already present)

DI should be implemented as a new service layer that:

Queries measurements through the same deterministic selection semantics as export (or explicitly defined DI semantics)

## Applies decision policies/templates (versioned definitions)

## Writes only decision snapshots / labels (never mutating source data)

## Produces structured outputs consumable by UI later

Recommended code placement (conceptual, not patches):

## psi/core/di/ for policy models + rules DSL + value functions + utilities

## psi/services/di/ for evaluation orchestration and snapshotting

## psi/web/routers/di.py and templates later (UI not in early phases)

## Roadmap overview

This is organized into focused versions. Each version has:

## Clear goal

## Required tasks

## Key “decisions we must make” (design decisions, not molecule decisions)

## Deliverables and “definition of done”

## Drift guards (what we must not expand into too early)

## v0.1 — DI Contract + Policy Spine (no UI, no new data types)

Goal: Define the DI “shape” and prove we can generate deterministic, explainable decision artifacts for one decision template.

## Tasks

Define DI input contract:

## decision_key, scope (molecule/batch), qc_mode, as_of_ts, context knobs

Define DI output schema (structured JSON):

state_of_evidence, gates, risk_flags, blockers, recommended_experiments, provenance

Define policy packaging:

## version string + content hash + human-readable changelog

Choose DI semantics for:

## QC interaction (strict/model_safe/none)

## missing data behavior (hold vs neutral)

## “ignored evidence” reporting

Define the first decision template: advance_to_in_vivo (qualitative gates, no hard numbers yet)

Create a minimal Experiment Catalog v0 (8–12 experiment types) with rationale mapping.

## Key decisions to make

## Batch-level vs molecule-level for each template (for in vivo: batch-level first)

## “Policy is data” format (YAML/JSON/py dataclasses) + hashing strategy

Which selection semantics DI uses for measurements (reuse exporter or define DI-specific)

## Definition of done

A DI run can be executed (headless) and produces a deterministic DecisionSnapshot output with policy hash and list of evidence used/ignored.

## Drift guards

## No ranking engine

## No holistic scoring

## No ML

## No UI

## v0.2 — State of Evidence (SoE) + Readiness Index (still no ranking)

Goal: Make DI immediately useful: summarize evidence completeness/quality and highlight blockers, even when no decision can be made.

## Tasks

Implement SoE summaries:

## measurement presence, QC status, recency, batch coverage, comparability flags

Implement “readiness” computation:

## completeness %, QC confidence, method comparability, reproducibility coverage

Implement blocker taxonomy:

missing_required, unreviewed_qc, conflicting_batches, method_incomparable, non_monotonic_interpretation_gap

## Key decisions

## What counts as “comparable” (method equality, conditions, units)

## How recency is defined (produced_at vs run_date fallback)

## Definition of done

For a molecule, DI can say: “we can’t decide yet because X,” and that list is correct and reproducible.

## Drift guards

## No fancy prioritization beyond deterministic blocker ordering

## No domain-specific magic numbers beyond “required vs optional”

## v0.3 — Next Best Experiments (NBE) Planner (deterministic “AI-like” value)

Goal: Suggest experiments with rationale to resolve the biggest blockers/uncertainties for advance_to_in_vivo.

## Tasks

## Implement mapping: blocker types → recommended experiments

Add “impact rationale” to each recommendation:

## what it resolves, what it produces, prerequisites, cost/time tier

Add optional “expected information gain” heuristic (deterministic):

## required gate missing > conflict > non-monotonic gap > low confidence

## Key decisions

## Experiment catalog ownership: how it’s versioned (tied to DI policy)

## Whether recommendations are per-batch vs per-molecule

## Definition of done

DI outputs a short ordered list of recommended experiments with explanations.

## Drift guards

## No probabilistic models

## No “optimal” claims—always framed as policy-guided recommendations

## v0.4 — “Non-monotonic metrics” & Value Functions (binding nuance formalized)

Goal: Encode metrics that are not “maximize/minimize” (e.g., binding vs internalization risk) without turning DI into scoring soup.

## Tasks

Implement value function types for measurements:

maximize, minimize, hard_cap, optimal_window, risk_zone, informational_only, context_dependent

Add companion-measurement requirements:

e.g., “internalization-sensitive binding requires internalization/surface expression timecourse to interpret tight KD”

Add risk flags tied to value functions:

## e.g., tight KD triggers “internalization risk zone” when companion data missing

## Key decisions

Which decision templates treat KD as:

## minimum bar vs risk zone vs informational only

## How to represent “interpretation gap” formally

## Definition of done

DI can explicitly say “KD is in a risk zone; interpretation requires X; until then we hold or flag.”

## Drift guards

## No hidden sigmoid curves or opaque transformations

## Every value function must be visible in the policy definition

## v0.5 — Controlled Shortlisting & Tie-breakers (ranking only when decision-ready)

Goal: Provide a shortlist/ranking for candidates only after gates pass and readiness threshold is met, using transparent, deterministic tie-break rules.

## Tasks

Define tie-break hierarchy for advance_to_in_vivo:

readiness completeness > QC confidence > purity/aggregation profile > reproducibility > potency/functional metric (contextual)

Implement deterministic ordering explanation:

## “A ranked above B because …”

Add “insufficient evidence to rank” state:

## DI refuses to rank when inputs are incomplete

## Key decisions

## Whether ranking is per-batch or per-molecule

## How to aggregate multiple READY batches into a molecule-level shortlist

## Definition of done

DI can rank a small set of candidates and provide a complete ordering rationale.

## Drift guards

## No weighted sum by default

## No “one score to rule them all”

## v0.6 — UI Surface (read-only, human-first)

Goal: Expose DI outputs in PSI without allowing DI to change data.

## Tasks

Add a DI “Decision” page per molecule and per batch:

## shows SoE, gates, risk flags, blockers, NBE recommendations

## Add “run DI” action (creates snapshot)

## Add snapshot browsing and diffing (compare outputs across policy versions)

## Key decisions

## Where DI sits in the molecule page UX (separate tab vs separate section)

## Snapshot retention and display conventions

## Definition of done

A scientist can run advance_to_in_vivo DI and understand the recommendation + rationale in <60 seconds.

## Drift guards

## No auto-actions (no auto-QC, no auto-“advance”)

## v1.0 — Multi-template DI (the “pre-decisions” you mentioned)

Goal: Add upstream decisions that naturally precede in vivo, and reuse shared sub-assessments.

## Likely templates (examples)

## select_for_engineering (fixable liabilities + best ROI experiments)

## ready_for_scaleup_screen (material readiness, reproducibility, basic stability)

ready_for_mechanism_validation (functional assay sufficiency, internalization interpretation completeness)

## Tasks

## Generalize policy/template framework

Shared sub-assessments library:

material readiness, mechanism readiness, reproducibility assessment, comparability assessment

## Template-specific experiment catalogs (or catalog tags)

## Key decisions

## Template dependency graph: which templates “feed” advance_to_in_vivo

## How to prevent policy sprawl

## Definition of done

DI offers a coherent ladder of decisions, not a pile of unrelated checklists.

## Drift guards

## No explosion of metrics without registry + provenance

## v1.1 — Outcome labeling + closed-loop learning readiness (still not ML)

Goal: Make DI self-improving by capturing “what happened” and “what was right/wrong.”

## Tasks

Define standard OutcomeLabel types:

in vivo efficacy outcome, PK/PD outcome, tolerability, manufacturability success, etc.

Add structured “post-hoc review” workflow:

## user marks whether DI recommendation was useful/incorrect and why

## Start building datasets for future ML/advanced modeling

## Key decisions

## What labels matter most early

## How to avoid hindsight bias

## Definition of done

PSI can accumulate a clean dataset linking decision snapshots to outcomes.

## v2.0 — Advanced analytics (CPU-friendly “AI-adjacent”)

Goal: Add profile comparisons and similarity search without heavy compute.

## Tasks

## Candidate profile vectors from normalized attributes

## Cohort comparisons (“this looks like historically good/bad profiles”)

## Simple clustering or nearest neighbors (CPU)

## Drift guards

## No opaque “model says so”—must remain explainable and tied to attributes

## v3.0 — True ML-assisted DI (optional, future hardware)

Goal: Introduce ML only where it clearly outperforms transparent rules and can be audited.

## Tasks

## Train models on labeled outcomes (from v1.1)

Use ML for:

## uncertainty estimation

## predictive flags (e.g., aggregation risk)

## experiment prioritization heuristics

Always wrap ML outputs with:

## “model confidence”

## feature importance / explanation

## policy controls (ML cannot override gates)

## Drift guards

## ML must not be the sole justification for a decision

## ML outputs are advisory and must remain exportable and versioned

## “Drift watch” checklist (use every iteration)

Before adding features, ask:

## Does this improve explainability?

## Does this preserve determinism and reproducibility?

## Does it remain context-aware (stage/route/modality)?

## Are we encoding biology explicitly (no hidden assumptions)?

## Are we improving decisions or just adding more numbers?

## Is it human-first (assist, not automate)?

## Immediate next step (to start v0.1 cleanly)

For advance_to_in_vivo, we should write (still brainstorming-level) the template skeleton:

## Context knobs (route/model/study intent)

## Gate categories (names only)

## Risk flag categories (including internalization-sensitive binding)

## Blocker taxonomy

## Experiment Catalog v0 list (names + what uncertainty each resolves)

## Output schema (field list)

That becomes the “DI constitution” for this first decision.

If you want, I can format the advance_to_in_vivo template skeleton next in the same checklist style (no numbers, no code)—so you can drop it into the doc as the first concrete section under v0.1.
