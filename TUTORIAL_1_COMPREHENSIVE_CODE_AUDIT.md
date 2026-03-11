# TUTORIAL_1_COMPREHENSIVE_CODE_AUDIT

## 1. Executive Summary
The current Tutorial 1 concept (Program + 3 initial molecules + builder-derived children + one advancing child) aligns well with PSI’s central scientist loop and would cover a large portion of molecule/program/task/data/evidence/claim/plan functionality.

It is not fully comprehensive against the current codebase.

Major uncovered or under-covered areas in the current concept are:
- DI/Decision snapshot lifecycle surfaces (`/di/run`, `/decisions/*`, verification/history/compare/export).
- QC/review flows (program review queue and per-measurement QC actions on data detail).
- Batch and file attachment workflows.
- Reports and upgrade-delta reporting surfaces.
- Portfolio + leadership narrative and export surfaces.
- Governance/lineage and legacy portfolio compatibility surfaces.
- Explicit board/workflow filter and operational triage behaviors.

Verdict: **Mostly, but missing important areas**.

## 2. Current Proposed Tutorial 1 Plan
Proposed structure reviewed:
- Create program `Tutorial 1`.
- Create molecules `TUT1-A`, `TUT1-B`, `TUT1-C`.
- Enter synthetic sequences and synthetic experimental data.
- Keep all 3 initial molecules blocked/non-advancing, with one clearly best.
- Use builder workflows to derive child molecules from best initial parent.
- Enter synthetic improved child data.
- Advance one child as leading candidate through broader PSI workflow.
- Include realistic synthetic scientist-entered interpretation text.

This is a strong base for molecule-centric workflow exercise.

## 3. Codebase Inventory of PSI User-Facing Capabilities

### 3.1 Core object types in code (models)
Primary data and decision objects are in [`psi/core/models.py`](/home/zach/psi_codex/psi/core/models.py):
- Program, Molecule, ProgramMembership.
- Batch.
- DataRecord (experiment/result capture object).
- Evidence.
- DecisionSnapshot (+ outcomes/labels/history associations).
- ExperimentTask.
- ScientificClaim (+ claim-evidence, claim-decision, claim-task links).
- ScientificPlan + ScientificPlanStep.
- Builder lineage artifacts: MoleculeDerivation, BuilderVariantSet, BuilderVariantSetMember.
- Sequence/annotation/compute artifacts: MoleculeComponent, SequenceEntity, Domain* and Property* entities.
- Portfolio + portfolio memberships (legacy and newer portfolio surfaces coexist).
- Report run entities.

Important note: there is no first-class `Experiment` model. In the user-facing flow, experiment result capture is represented through `DataRecord` and extracted measurements.

### 3.2 Major routers and user surfaces
Router inclusion is in [`psi/web/app.py`](/home/zach/psi_codex/psi/web/app.py). Major route families:
- Programs: [`psi/web/routers/programs.py`](/home/zach/psi_codex/psi/web/routers/programs.py)
  - Program detail, board, workflow center, narrative pages, task operations, review queue bulk actions.
- Molecules: [`psi/web/routers/molecules.py`](/home/zach/psi_codex/psi/web/routers/molecules.py)
  - Molecule workspace, compute/numbering/immunogenicity/domain actions, file attachment.
- Builder: [`psi/web/routers/builder.py`](/home/zach/psi_codex/psi/web/routers/builder.py)
  - Clone, point mutation, CDR builder, variant-set generation/detail, suggested task handoff.
- Data/results: [`psi/web/routers/data_records.py`](/home/zach/psi_codex/psi/web/routers/data_records.py)
  - Data list/new/edit/detail, bulk import, QC approve/reject.
- Evidence: [`psi/web/routers/evidence.py`](/home/zach/psi_codex/psi/web/routers/evidence.py)
  - Evidence list/new/edit/detail, citation linking, optional inline data creation.
- Claims: [`psi/web/routers/claims.py`](/home/zach/psi_codex/psi/web/routers/claims.py)
  - Claim list/new/detail/status transition.
- Plans: [`psi/web/routers/plans.py`](/home/zach/psi_codex/psi/web/routers/plans.py)
  - Plan list/new/detail, plan transition, plan/step task instantiation.
- Decisions + DI run:
  - [`psi/web/routers/di.py`](/home/zach/psi_codex/psi/web/routers/di.py)
  - [`psi/web/routers/decisions.py`](/home/zach/psi_codex/psi/web/routers/decisions.py)
- Reports: [`psi/web/routers/reports.py`](/home/zach/psi_codex/psi/web/routers/reports.py)
- Portfolio intelligence + narrative exports:
  - [`psi/web/routers/portfolio.py`](/home/zach/psi_codex/psi/web/routers/portfolio.py)
  - [`psi/web/routers/portfolios.py`](/home/zach/psi_codex/psi/web/routers/portfolios.py) (legacy portfolio CRUD/membership).
- Additional: batches, files, lineage, search, qc endpoints.

### 3.3 Major templates/surfaces
Global shell and IA:
- [`psi/web/templates/base.html`](/home/zach/psi_codex/psi/web/templates/base.html)

Primary scientist surfaces:
- Molecule workspace: [`psi/web/templates/molecules/detail.html`](/home/zach/psi_codex/psi/web/templates/molecules/detail.html)
- Program strategy/detail: [`psi/web/templates/programs/detail.html`](/home/zach/psi_codex/psi/web/templates/programs/detail.html)
- Program board: [`psi/web/templates/programs/board.html`](/home/zach/psi_codex/psi/web/templates/programs/board.html)
- Program workflow center: [`psi/web/templates/programs/workflow.html`](/home/zach/psi_codex/psi/web/templates/programs/workflow.html)
- Data capture/detail: [`psi/web/templates/data/form.html`](/home/zach/psi_codex/psi/web/templates/data/form.html), [`psi/web/templates/data/detail.html`](/home/zach/psi_codex/psi/web/templates/data/detail.html)
- Evidence capture/detail: [`psi/web/templates/evidence/form.html`](/home/zach/psi_codex/psi/web/templates/evidence/form.html), [`psi/web/templates/evidence/detail.html`](/home/zach/psi_codex/psi/web/templates/evidence/detail.html)
- Claims/plans detail: [`psi/web/templates/claims/detail.html`](/home/zach/psi_codex/psi/web/templates/claims/detail.html), [`psi/web/templates/plans/detail.html`](/home/zach/psi_codex/psi/web/templates/plans/detail.html)
- Builder workspace family: [`psi/web/templates/builder/*.html`](/home/zach/psi_codex/psi/web/templates/builder)
- Portfolio overview: [`psi/web/templates/portfolio/overview.html`](/home/zach/psi_codex/psi/web/templates/portfolio/overview.html)
- Decision + report templates: [`psi/web/templates/decisions/*.html`](/home/zach/psi_codex/psi/web/templates/decisions), [`psi/web/templates/reports/*.html`](/home/zach/psi_codex/psi/web/templates/reports)

### 3.4 Major service modules relevant to tutorial workflows
- Molecule/program/workflow orchestration:
  - [`psi/services/molecules.py`](/home/zach/psi_codex/psi/services/molecules.py)
  - [`psi/services/programs.py`](/home/zach/psi_codex/psi/services/programs.py)
  - [`psi/services/workflow_center.py`](/home/zach/psi_codex/psi/services/workflow_center.py)
  - [`psi/services/dev_board.py`](/home/zach/psi_codex/psi/services/dev_board.py)
- Loop entities and transitions:
  - [`psi/services/experiment_tasks.py`](/home/zach/psi_codex/psi/services/experiment_tasks.py)
  - [`psi/services/data_records.py`](/home/zach/psi_codex/psi/services/data_records.py)
  - [`psi/services/evidence.py`](/home/zach/psi_codex/psi/services/evidence.py)
  - [`psi/services/claims.py`](/home/zach/psi_codex/psi/services/claims.py)
  - [`psi/services/plans.py`](/home/zach/psi_codex/psi/services/plans.py)
- Decision/intelligence/projection:
  - [`psi/services/decisions.py`](/home/zach/psi_codex/psi/services/decisions.py)
  - [`psi/services/insight_engine.py`](/home/zach/psi_codex/psi/services/insight_engine.py)
  - [`psi/services/trajectory.py`](/home/zach/psi_codex/psi/services/trajectory.py)
  - [`psi/services/portfolio.py`](/home/zach/psi_codex/psi/services/portfolio.py)
  - [`psi/services/narratives.py`](/home/zach/psi_codex/psi/services/narratives.py)
- Builder/lineage:
  - [`psi/services/builder.py`](/home/zach/psi_codex/psi/services/builder.py)
  - [`psi/services/builder_ops.py`](/home/zach/psi_codex/psi/services/builder_ops.py)

## 4. Coverage Matrix: Proposed Tutorial vs PSI Capabilities

| Capability area | Exists in code | User-facing | Covered by current Tutorial 1 concept | Notes |
|---|---|---|---|---|
| Program creation + molecule creation | Yes | Yes | Yes | Core opening steps aligned (`/programs/new`, `/molecules/new`). |
| Molecule workspace loop (tasks/claims/plans/data/evidence links) | Yes | Yes | Mostly | Concept covers this but should explicitly include each linked panel/action path. |
| Program board execution triage | Yes | Yes | Partial | Concept implies progression but does not explicitly require board usage, card actions, filters. |
| Program workflow center buckets | Yes | Yes | Partial | Should explicitly exercise ready/in-progress/blocked/awaiting-data/completed. |
| Task lifecycle transitions | Yes | Yes | Partial | Needs explicit status transitions and owner/due/urgency usage. |
| Task -> data handoff | Yes | Yes | Partial | Should explicitly use `create-and-start-data` and `task_id` handoff paths. |
| Data capture + measurement review + QC actions | Yes | Yes | Partial | Concept says synthetic data, but not QC approval/rejection/measurement review paths. |
| Evidence creation with citations | Yes | Yes | Yes/Partial | Likely covered, but must include citation IDs and detail-page re-entry behavior. |
| Claim creation + transition + evidence/task/decision links | Yes | Yes | Partial | Current concept mentions interpretation text, not explicit claim transitions/linking. |
| Plan creation + transitions + step instantiation | Yes | Yes | Partial | Must explicitly create plans and instantiate steps to tasks. |
| Trajectory heuristic surfaces | Yes | Yes | Partial | Should include explicit “heuristic estimate” usage from molecule/board/claim. |
| Builder clone / point mutation / CDR / variant set | Yes | Yes | Partial | Current concept only says “use builder.” To be comprehensive it should hit all major builder modes. |
| Lineage tracking (parent-child derivation + lineage pages) | Yes | Yes | Partial | Parent->child concept aligns; should explicitly inspect lineage surfaces. |
| DI run + decision snapshot lifecycle | Yes | Yes | No | Not currently included in concept; major gap. |
| Decision verification/history/compare/export | Yes | Yes | No | Not covered by current concept. |
| Reports generation + report detail + upgrade delta | Yes | Yes | No | Not covered. |
| Portfolio intelligence + narrative + export | Yes | Yes | No/Partial | Program-level tutorial may skip cross-program surfaces unless designed in. |
| Legacy portfolios registry + membership | Yes | Yes | No | Likely optional for scientist tutorial, but exists and is user-facing. |
| Batches and file upload/download surfaces | Yes | Yes | Partial/No | Concept implies data but not explicit batch/file flows. |
| Search/registry APIs and cross-object navigation | Yes | Yes | Partial | Not explicitly planned. |
| Governance/audit views on molecule/program | Yes | Yes | Partial | Should include history/audit tabs and decisions lineage review. |

## 5. Evaluation of the A/B/C -> best parent -> child variants -> lead candidate structure
The structure is strongly aligned with current PSI behavior.

Why it fits code:
- Parent-child derivation is first-class in builder workflows (`/builder/clone`, `/builder/point-mutation`, `/builder/cdr-builder`, `/builder/variant-set`) and lineage models.
- Molecule detail and program board/workflow surfaces already expect comparative triage across molecules.
- “Best among blocked” maps well to board grouping and trajectory/insight recommendation patterns.
- Suggested experiment -> task creation is wired through molecule and builder suggested-task flows.

What needs tightening for full alignment:
- “Best initial parent” should be selected using explicit PSI-visible signals (board card blockers, open-task burden, missing metrics, latest DI snapshot context), not only narrative judgment.
- Child generation should include at least one variant family operation (variant set) plus one targeted edit path (point mutation or CDR) to fully exercise builder capabilities.
- Lead-candidate progression should include explicit task, data, evidence, claim, plan, and decision checkpoints rather than only improved assay values.

Conclusion: the A/B/C -> best-parent -> children -> lead structure is a good backbone for PSI specifically.

## 6. Actual Code-Backed Development Progression Path in PSI
A realistic “all the way through” path in current PSI code can be represented as:

1. Program setup and candidate set
- Create program and attach molecules/memberships.
- Review program detail and board grouping.

2. Operational work definition
- Create ExperimentTasks from board suggestions, molecule pages, builder suggested-task, and plan instantiation.
- Use lifecycle transitions (`planned`, `in_progress`, `blocked`, `done`) plus owner/due/urgency.

3. Result capture
- Start result capture from task/workflow handoff (`/data/new` with `task_id`, `return_to`, source context).
- Enter result metadata, params/results JSON, run date, notes.

4. QC and interpretation queue
- Review extracted measurements and per-measurement QC actions on data detail.
- Use program review queue bulk and per-record approvals/rejections.

5. Evidence interpretation
- Create evidence records citing data record IDs.
- Use evidence detail to navigate back to program/molecule/workflow context.

6. Claim maturity progression
- Create/transition claims.
- Link evidence (supporting/contradicting/contextual), link tasks, optionally link decisions.

7. Plan progression and execution bridge
- Create/transition plans.
- Instantiate whole plan or individual steps into tasks.

8. Decision intelligence checkpoint
- Run DI (`/di/run` or legacy decision run surface) and inspect decision snapshots.
- Use decision history/compare/verify/outcome labeling/export as governance checkpoints.

9. Portfolio/reporting checkpoints
- Inspect portfolio overview/narrative for program impact.
- Generate report runs and inspect report detail/upgrade delta.

This is the practical code-backed “development process” breadth currently available.

## 7. Missing Coverage / Blind Spots
Current Tutorial 1 concept misses or under-specifies these important areas:

- Decision system and governance
  - DI run and decision snapshots are core PSI capabilities; current concept does not explicitly include them.
  - Missing compare/history/verify/export/outcome-label actions on decisions.

- QC flow coverage
  - Current concept says “enter data” but does not include per-measurement QC or review queue actions.

- Batch/file traceability
  - Batch lifecycle and file upload/download/citation surfaces are not explicitly in scope.

- Plan-step instantiation pathway
  - Current concept includes plans but not explicit “plan step -> task” instantiation route coverage.

- Claim linkage depth
  - Current concept includes claims generally, but not explicit claim-evidence directionality and task/decision links.

- Builder breadth
  - Concept includes derived children but not explicit coverage of clone vs point mutation vs CDR vs variant set pages.

- Cross-program portfolio and leadership surfaces
  - With one tutorial program, portfolio prioritization and narrative value are weakly exercised unless additional synthetic context is included.

- Report generation surfaces
  - Report creation and upgrade delta views are unaddressed.

- Legacy but user-facing compatibility surfaces
  - `/portfolios` (legacy) exists and is user-facing; likely optional for tutorial goals but currently uncovered.

## 8. Recommended Revisions to Make Tutorial 1 Fully Comprehensive
Keep the current backbone, but add explicit coverage checkpoints.

Recommended adjustments:
- Keep 3 initial molecules (`TUT1-A/B/C`) and select one best blocked parent using explicit board/workflow/insight cues.
- Require explicit task lifecycle walkthrough:
  - create, start, block/unblock, complete, owner/due/urgency updates.
- Require task-origin result capture at least once via workflow handoff (`task_id`-aware path).
- Require at least one QC review pass (approve and reject examples on synthetic measurements).
- Require explicit evidence citation of created data records.
- Require claim status transitions and at least one supporting + one contradicting evidence link.
- Require plan creation with ordered steps and step instantiation into tasks.
- Require at least one DI run and decision snapshot review (plus at least one history/compare/verify or outcome-label step).
- Require at least one builder variant family flow, not only a single child edit flow.
- Require lineage inspection of parent/child molecules.
- Require one report generation path and one portfolio overview pass.
- Optionally include a short “compatibility surfaces” appendix for legacy portfolios and file registry.

## 9. Suggested Final Tutorial Phase Outline

### Phase 1: Program and baseline candidates
- Create `Tutorial 1` program.
- Create `TUT1-A/B/C` with synthetic sequences and initial context.
- Open program detail and board; inspect initial grouping and blockers.

### Phase 2: Baseline execution loop
- Create tasks from board/molecule suggestions.
- Move tasks through status buckets in program workflow.
- Capture synthetic result records from task-aware data entry.
- Perform QC/review actions.

### Phase 3: Evidence and interpretation
- Create evidence citing those results.
- Add realistic synthetic interpretation text.
- Create claims, link evidence with directionality, transition claim states.

### Phase 4: Planning and controlled progression
- Create plans tied to molecule/claim scope.
- Instantiate selected steps into tasks.
- Demonstrate plan status transitions and feedback from recent results/evidence.

### Phase 5: Parent selection and builder-derived children
- Use board/workflow/insight cues to select best initial parent.
- Generate children through builder (point mutation and variant set at minimum; optionally clone/CDR path).
- Capture improved synthetic data/evidence for children.

### Phase 6: Lead-candidate advancement checkpoint
- Select one child as tutorial lead based on explicit PSI-visible signals.
- Show lead progression through tasks, results, evidence, claims, and plans.
- Run DI decision checkpoint and review decision snapshot details.

### Phase 7: Governance, reporting, and portfolio readout
- Review decision history/compare/verify and add outcome labels.
- Generate at least one report and inspect detail.
- Open portfolio overview/narrative/export surfaces to show cross-surface story.
- Review lineage and audit/history surfaces for traceability closure.

## 10. Appendix: Key code locations examined

Application and routing:
- [`psi/web/app.py`](/home/zach/psi_codex/psi/web/app.py)
- [`psi/web/routers/programs.py`](/home/zach/psi_codex/psi/web/routers/programs.py)
- [`psi/web/routers/molecules.py`](/home/zach/psi_codex/psi/web/routers/molecules.py)
- [`psi/web/routers/builder.py`](/home/zach/psi_codex/psi/web/routers/builder.py)
- [`psi/web/routers/data_records.py`](/home/zach/psi_codex/psi/web/routers/data_records.py)
- [`psi/web/routers/evidence.py`](/home/zach/psi_codex/psi/web/routers/evidence.py)
- [`psi/web/routers/claims.py`](/home/zach/psi_codex/psi/web/routers/claims.py)
- [`psi/web/routers/plans.py`](/home/zach/psi_codex/psi/web/routers/plans.py)
- [`psi/web/routers/decisions.py`](/home/zach/psi_codex/psi/web/routers/decisions.py)
- [`psi/web/routers/di.py`](/home/zach/psi_codex/psi/web/routers/di.py)
- [`psi/web/routers/reports.py`](/home/zach/psi_codex/psi/web/routers/reports.py)
- [`psi/web/routers/portfolio.py`](/home/zach/psi_codex/psi/web/routers/portfolio.py)
- [`psi/web/routers/portfolios.py`](/home/zach/psi_codex/psi/web/routers/portfolios.py)
- [`psi/web/routers/batches.py`](/home/zach/psi_codex/psi/web/routers/batches.py)
- [`psi/web/routers/files.py`](/home/zach/psi_codex/psi/web/routers/files.py)
- [`psi/web/routers/lineage.py`](/home/zach/psi_codex/psi/web/routers/lineage.py)
- [`psi/web/routers/search.py`](/home/zach/psi_codex/psi/web/routers/search.py)
- [`psi/web/routers/qc.py`](/home/zach/psi_codex/psi/web/routers/qc.py)

Core models and services:
- [`psi/core/models.py`](/home/zach/psi_codex/psi/core/models.py)
- [`psi/services/molecules.py`](/home/zach/psi_codex/psi/services/molecules.py)
- [`psi/services/programs.py`](/home/zach/psi_codex/psi/services/programs.py)
- [`psi/services/workflow_center.py`](/home/zach/psi_codex/psi/services/workflow_center.py)
- [`psi/services/dev_board.py`](/home/zach/psi_codex/psi/services/dev_board.py)
- [`psi/services/program_board.py`](/home/zach/psi_codex/psi/services/program_board.py)
- [`psi/services/experiment_tasks.py`](/home/zach/psi_codex/psi/services/experiment_tasks.py)
- [`psi/services/data_records.py`](/home/zach/psi_codex/psi/services/data_records.py)
- [`psi/services/evidence.py`](/home/zach/psi_codex/psi/services/evidence.py)
- [`psi/services/claims.py`](/home/zach/psi_codex/psi/services/claims.py)
- [`psi/services/plans.py`](/home/zach/psi_codex/psi/services/plans.py)
- [`psi/services/trajectory.py`](/home/zach/psi_codex/psi/services/trajectory.py)
- [`psi/services/insight_engine.py`](/home/zach/psi_codex/psi/services/insight_engine.py)
- [`psi/services/decisions.py`](/home/zach/psi_codex/psi/services/decisions.py)
- [`psi/services/portfolio.py`](/home/zach/psi_codex/psi/services/portfolio.py)
- [`psi/services/narratives.py`](/home/zach/psi_codex/psi/services/narratives.py)
- [`psi/services/reports_v3.py`](/home/zach/psi_codex/psi/services/reports_v3.py)
- [`psi/services/builder.py`](/home/zach/psi_codex/psi/services/builder.py)
- [`psi/services/builder_ops.py`](/home/zach/psi_codex/psi/services/builder_ops.py)

Templates and UX shell:
- [`psi/web/templates/base.html`](/home/zach/psi_codex/psi/web/templates/base.html)
- [`psi/web/templates/programs/detail.html`](/home/zach/psi_codex/psi/web/templates/programs/detail.html)
- [`psi/web/templates/programs/board.html`](/home/zach/psi_codex/psi/web/templates/programs/board.html)
- [`psi/web/templates/programs/workflow.html`](/home/zach/psi_codex/psi/web/templates/programs/workflow.html)
- [`psi/web/templates/molecules/detail.html`](/home/zach/psi_codex/psi/web/templates/molecules/detail.html)
- [`psi/web/templates/molecules/partials/*.html`](/home/zach/psi_codex/psi/web/templates/molecules/partials)
- [`psi/web/templates/builder/*.html`](/home/zach/psi_codex/psi/web/templates/builder)
- [`psi/web/templates/data/form.html`](/home/zach/psi_codex/psi/web/templates/data/form.html)
- [`psi/web/templates/data/detail.html`](/home/zach/psi_codex/psi/web/templates/data/detail.html)
- [`psi/web/templates/evidence/form.html`](/home/zach/psi_codex/psi/web/templates/evidence/form.html)
- [`psi/web/templates/evidence/detail.html`](/home/zach/psi_codex/psi/web/templates/evidence/detail.html)
- [`psi/web/templates/claims/detail.html`](/home/zach/psi_codex/psi/web/templates/claims/detail.html)
- [`psi/web/templates/plans/detail.html`](/home/zach/psi_codex/psi/web/templates/plans/detail.html)
- [`psi/web/templates/portfolio/overview.html`](/home/zach/psi_codex/psi/web/templates/portfolio/overview.html)
- [`psi/web/templates/decisions/*.html`](/home/zach/psi_codex/psi/web/templates/decisions)
- [`psi/web/templates/reports/*.html`](/home/zach/psi_codex/psi/web/templates/reports)
- [`psi/web/ui_surfaces.py`](/home/zach/psi_codex/psi/web/ui_surfaces.py)
- [`psi/web/handoff_context.py`](/home/zach/psi_codex/psi/web/handoff_context.py)

Tests consulted for workflow intent and exercised surfaces:
- [`tests/test_workflow_center_service.py`](/home/zach/psi_codex/tests/test_workflow_center_service.py)
- [`tests/test_handoff_context.py`](/home/zach/psi_codex/tests/test_handoff_context.py)
- [`tests/test_suggested_experiment_task_creation.py`](/home/zach/psi_codex/tests/test_suggested_experiment_task_creation.py)
- [`tests/test_plan_task_instantiation.py`](/home/zach/psi_codex/tests/test_plan_task_instantiation.py)
- [`tests/test_claims_service.py`](/home/zach/psi_codex/tests/test_claims_service.py)
- [`tests/test_plans_service.py`](/home/zach/psi_codex/tests/test_plans_service.py)
- [`tests/test_trajectory_service.py`](/home/zach/psi_codex/tests/test_trajectory_service.py)
- [`tests/test_program_board_filters.py`](/home/zach/psi_codex/tests/test_program_board_filters.py)
- [`tests/test_program_narrative_surface.py`](/home/zach/psi_codex/tests/test_program_narrative_surface.py)
- [`tests/test_portfolio_narrative_surface.py`](/home/zach/psi_codex/tests/test_portfolio_narrative_surface.py)

---

## Final Verdict
**Is the current Tutorial 1 concept comprehensive enough to exercise the PSI codebase as it exists today?**

**Mostly, but missing important areas.**

Justification:
- The concept strongly covers the core molecule-centric scientist loop and builder-driven progression.
- It does not yet explicitly cover major implemented PSI capability families: DI/decision governance, QC review behavior, report generation, portfolio/leadership narrative/export surfaces, and some traceability/governance compatibility surfaces.
- With the recommended additions above, Tutorial 1 can become a true end-to-end user tutorial plus broad PSI stress test.
