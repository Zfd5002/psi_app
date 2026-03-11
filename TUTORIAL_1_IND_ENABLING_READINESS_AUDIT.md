# TUTORIAL_1_IND_ENABLING_READINESS_AUDIT

## 1. Executive Summary
PSI currently has strong deterministic decision infrastructure, governance/reporting surfaces, and progression semantics for **scale-up screening readiness** and **advance-to-in-vivo readiness**. It does **not** currently expose an explicit first-class endpoint named or modeled as "IND-enabling green light" in DI template catalogs, policy packages, decision keys, report types, or dedicated stage enums.

In practice, a tutorial can reach a rigorous, code-grounded "go/no-go for next phase" determination using existing DI + decision snapshot + governance/report workflows. However, mapping that endpoint specifically to "green light for IND-enabling studies" requires interpretation on top of generic/adjacent primitives (especially `ready_for_scaleup_screen` and `advance_to_in_vivo`), not an explicit IND-enabling construct.

Net: PSI can support this endpoint **partially/implicitly**, but important late-stage semantics remain unmodeled as explicit product primitives.

## 2. Question Under Audit
Can PSI, as currently implemented, support a tutorial that ends with a **code-grounded determination** that a molecule should receive the **green light for IND-enabling studies**?

This audit distinguishes:
- explicit product support
- implicit support via generic primitives
- partial support with missing semantics
- no meaningful support

## 3. Codebase Inventory Relevant to Late-Stage / Pre-IND Progression

### 3.1 DI decision template inventory (canonical)
- `psi/core/di/catalogs/template_catalog_v0_1.json`
  - Registered decision templates are centered on:
    - `advance_to_in_vivo` (current: `v0.5`)
    - `ready_for_scaleup_screen` (current: `v0.2`)
- `psi/core/di/catalogs/template_prerequisites_v0_2.json`
  - `advance_to_in_vivo.v0_5` depends on `ready_for_scaleup_screen.v0_2`.

### 3.2 Progress policy and milestone semantics
- `psi/core/di/catalogs/progress_policy_v0_2.json`
  - Defines progress milestones and maps readiness checks to DI templates.
  - Includes milestone language around quality/manufacturability/screening readiness (for example `scaleup_ready`) and in-vivo transition readiness (`in_vivo_ready`).
  - No explicit IND-enabling milestone identifier.

### 3.3 Policy packages and DI evaluators
- Policy JSON:
  - `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
  - `psi/core/di/policies/ready_for_scaleup_screen_v0_2.json`
- Evaluator implementation:
  - `psi/services/di/templates/advance_to_in_vivo.py`
  - `psi/services/di/templates/ready_for_scaleup_screen.py`
- Registry wiring:
  - `psi/services/di/templates/registry.py`

These form deterministic gate/blocker/risk-based decisions for specific keys. No explicit "IND-enabling" decision key exists.

### 3.4 Decision snapshots / governance records
- `psi/core/models.py`
  - `DecisionSnapshot`, review labels (`OutcomeLabel`), report-related records (`ReportRun`), plus claims/plans/tasks.
- `psi/services/decisions.py`
  - Decision history, labeling, verification/review semantics.
  - Available outcome labels are generic QA/review labels (e.g., correctness/risk/data sufficiency), not stage-authorizing labels such as IND-enabling authorization.

### 3.5 User-facing decision and DI surfaces
- DI run surface:
  - Router: `psi/web/routers/di.py`
  - Template: `psi/web/templates/di/run.html`
  - Decision keys selectable from registry-backed templates.
- Decision surfaces:
  - Router: `psi/web/routers/decisions.py`
  - Templates include detail/history/compare/verify/export flows.

### 3.6 Reporting surfaces relevant to late-stage review
- Router/services:
  - `psi/web/routers/reports.py`
  - `psi/services/reports_v3.py`
  - `psi/services/report_engine.py`
- Templates:
  - `psi/web/templates/reports/board_program_v3.html`
  - `psi/web/templates/reports/board_molecule_v3.html`
  - `psi/web/templates/reports/board_comparison_v3.html`
  - `psi/web/templates/reports/detail.html`
  - `psi/web/templates/reports/upgrade_delta_detail.html`

Report families cover program, molecule, and comparative reporting with policy/snapshot context and risk/readiness narratives, but no explicit report type with a native "IND-enabling green light" schema.

### 3.7 Molecule/program stage framing in UI services
- `psi/services/molecule_header.py`
  - Computes `progress_stage` and advisory text from milestone/DI readiness context.
- `psi/web/templates/molecules/detail.html`
  - Renders the derived stage/progress framing.

This is progression-aware, but still mapped to current DI template semantics rather than explicit IND endpoint semantics.

## 4. Decision-System Findings

### 4.1 What is explicitly implemented
- Deterministic DI decision execution for registered decision keys.
- Gate-level pass/fail/blocked behavior.
- Snapshot persistence, comparison, verification, and export.
- Prerequisite chaining between available decision templates.

### 4.2 What is not explicitly implemented
- No DI template key explicitly named for IND-enabling authorization/readiness.
- No dedicated policy package representing IND-enabling gating criteria as a first-class template.
- No dedicated terminal decision-state vocabulary explicitly tied to IND-enabling progression.

### 4.3 Practical implication
The decision system can produce strong code-grounded "ready/not-ready" determinations for currently modeled stages (notably scale-up screening and in-vivo transition). A tutorial can map this to a late-stage go/no-go narrative, but the specific IND-enabling endpoint is inferred, not directly modeled.

## 5. Report/Governance Findings

### 5.1 Reporting strengths relevant to late-stage review
- Program/molecule/comparative report generation exists and is user-facing.
- Reports can aggregate readiness, blocker, and trend context from DI/snapshots and related surfaces.
- Governance utilities (history/compare/verify/export) support review traceability.

### 5.2 Report limitations for explicit IND endpoint
- No distinct report schema/type whose explicit output field is "IND-enabling green light: yes/no".
- No explicit built-in report taxonomy centered on late preclinical IND package readiness.

### 5.3 Governance realism for tutorial use
A realistic "governance checkpoint" can be built in tutorial flow using existing report and decision surfaces, but the endpoint label should be framed carefully (for example, recommendation for next-stage planning) unless PSI adds explicit IND-enabling semantics.

## 6. Explicit vs Implicit Support Analysis

### Explicit support (present)
- Deterministic DI decisions for registered progression templates.
- Structured blockers/risks/readiness logic.
- Snapshot-based governance and report generation.
- User-facing routes/templates for decision and report workflows.

### Implicit support (possible via current primitives)
- A tutorial can treat a combination of:
  - `ready_for_scaleup_screen`
  - `advance_to_in_vivo`
  - supporting data/evidence/claims/plans/tasks
  - governance report review
  as a strong proxy for late-stage confidence.

### Missing explicit late-stage semantics
- No first-class "IND-enabling" decision template.
- No explicit stage enum/status in models tied to IND authorization semantics.
- No explicit report output contract for IND-enabling recommendation.

Conclusion of this section: support is meaningful but not fully explicit for the exact requested endpoint.

## 7. Tutorial Design Implication
For Tutorial 1, ending with a literal "IND-enabling green light" claim as if PSI natively models that endpoint would overstate current implementation.

Best code-aligned endpoint options:
1. End at **preclinical candidate recommendation for IND-enabling planning**, grounded in current DI + governance + reporting outputs.
2. Or end at **strong go/no-go decision for next modeled phase** (scale-up/in-vivo readiness), with explicit note that IND-enabling itself is downstream and not first-class in current template catalog.

This preserves determinism and code fidelity while still delivering a realistic leadership/scientist decision checkpoint.

## 8. Final Verdict

**Question:** “Can PSI currently support a tutorial that ends with a code-grounded green light for IND-enabling studies?”

**Answer:** **Partially, but important gaps remain**

### Justification
- PSI **does** provide deterministic decisioning, snapshot governance, and reporting infrastructure robust enough for serious staged progression decisions.
- PSI **does** model readiness transitions around currently implemented templates (`ready_for_scaleup_screen`, `advance_to_in_vivo`) and can support auditable go/no-go narratives.
- PSI **does not** currently expose an explicit IND-enabling decision template, explicit IND endpoint stage semantics, or dedicated IND-focused report schema/output.

Therefore, a tutorial can reach a credible, code-grounded **recommendation toward IND-enabling planning**, but not a fully explicit built-in product endpoint labeled as an IND-enabling green light without interpretive bridging.

## 9. Appendix: Key code locations examined

### DI / policy / progress catalogs
- `psi/core/di/catalogs/template_catalog_v0_1.json`
- `psi/core/di/catalogs/template_prerequisites_v0_2.json`
- `psi/core/di/catalogs/progress_policy_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_2.json`

### DI template execution
- `psi/services/di/templates/registry.py`
- `psi/services/di/templates/advance_to_in_vivo.py`
- `psi/services/di/templates/ready_for_scaleup_screen.py`

### Decision/governance core
- `psi/core/models.py`
- `psi/services/decisions.py`
- `psi/web/routers/di.py`
- `psi/web/routers/decisions.py`
- `psi/web/templates/di/run.html`
- `psi/web/templates/decisions/detail.html`

### Reporting / governance surfaces
- `psi/web/routers/reports.py`
- `psi/services/reports_v3.py`
- `psi/services/report_engine.py`
- `psi/web/templates/reports/board_program_v3.html`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/upgrade_delta_detail.html`

### Progress/stage rendering context
- `psi/services/molecule_header.py`
- `psi/web/templates/molecules/detail.html`

### Additional docs/tests consulted for terminology/coverage checks
- `docs/DI_CONSTITUTION.md`
- `docs/DI_MISSION_AND_ROADMAP_V3.md`
- repository-wide search across `psi/`, `docs/`, `tests/` for: `IND`, `ind-enabling`, `candidate nomination`, `scaleup`, `tox`, `PK`, `safety`, `preclinical`, `green light`.
