# Leadership / Investor Narrative Layer

## Purpose
The Narrative layer provides deterministic, leadership-readable interpretations over PSI scientific and operational state.

It answers:
- What is the program trying to prove?
- What supports current direction?
- What remains uncertain or risky?
- What milestone is most likely next?
- Where is the portfolio strongest or most constrained?

## Narrative Objects
### Program Narrative
Generated via `psi/services/narratives.py::build_program_narrative(...)`.

Core fields include:
- `scientific_thesis`
- `current_state_summary`
- `strongest_support`
- `major_uncertainties`
- `active_risks`
- `active_plans`
- `next_milestone`
- `milestone_rationale`
- `overall_stage`
- `confidence_summary`
- `milestone_framing`
- link/anchor blocks to claims, plans, trajectory opportunities

### Portfolio Narrative
Generated via `psi/services/narratives.py::build_portfolio_narrative(...)`.

Core fields include:
- `strongest_programs`
- `most_blocked_programs`
- `key_bottlenecks`
- `highest_value_plans`
- `near_term_inflection_points`
- `near_term_inflection_rows`
- `task_burden_summary`
- `evidence_gap_summary`
- `leadership_cards`

## Derivation Model
Narratives are derived from existing PSI read models only:
- Programs / Molecules
- DecisionSnapshot outputs (read-only)
- ScientificClaim state and links
- ScientificPlan / ScientificPlanStep
- ExperimentTask
- Trajectory candidates
- Portfolio rollups

No narrative generation path mutates scientific truth or operational truth.

## Architectural Boundaries
The layer must not:
- modify DI semantics
- modify snapshot hashing
- write narrative text into DecisionSnapshot payloads
- create evidence rows
- mutate claim/task/plan state during generation
- use nondeterministic LLM text generation for core summaries

## UI Surfaces
- Program detail narrative panel
- Program full narrative page: `/programs/{id}/narrative`
- Program narrative export: `/programs/{id}/narrative/export`
- Portfolio narrative sections on `/portfolio`
- Portfolio narrative export: `/portfolio/narrative/export`

Brief mode is available for leadership scanability:
- `/programs/{id}/narrative?view=brief`
- `/portfolio?view=brief`

## Determinism Rules
- Stable sorting in supporting services (claims, plans, trajectory, portfolio)
- Templated narrative block generation from explicit counters/lists
- No hidden iteration-order dependencies
- Regression tests enforce deterministic output equality and non-mutation boundaries

## Extension Points
Future additive extensions can include:
- periodic persisted narrative snapshots for board meeting history
- audience profiles (scientist/exec/investor) with deterministic templates
- milestone probability framing from deterministic portfolio heuristics

Any extension must preserve DI/evidence/claim/task truth boundaries.
