# PSI UX Philosophy

## 1. Core Product Principle
PSI should feel like a scientist assistant, not a data-entry ledger. The interface should continuously help users understand development posture and next action.

## 2. Page Design Principle
Every primary page should answer one question near the top: **What do I do next?**

## 3. Workflow Principle
The default scientist loop is:
`Enter experiment result -> PSI updates assessment -> Scientist chooses next action`.

## 4. Context Principle
If a user launches a surface from a program or molecule context, that context should be preserved by default. Global views should remain available as an explicit user choice.

## 5. Information Hierarchy Principle
Prioritize content in this order:
1. Day-to-day scientist workflow
2. Optional interpretation and planning
3. Governance, audit, and deep technical detail

## 6. Progressive Disclosure Principle
Advanced information must stay available, but should be collapsed or demoted by default unless the scientist intentionally opens it.

## 7. Result Review Principle
Scientists reason molecule-first. Molecule-level result review entry points should be obvious, while batch-first drill-down remains available for deep investigation.

## 8. Assessment Principle
Current development posture, blockers, and recommended next step should be visible and actionable near the top of program and molecule operating surfaces.

## 9. Governance Compatibility Principle
Usability improvements must preserve PSI’s deterministic guarantees:
- immutable snapshots
- replayability
- policy provenance and policy-as-data contracts

## 10. Tutorial Validation Principle
Tutorial-driven execution is a core UX validation method. If a first-time scientist cannot complete a realistic walkthrough smoothly, the product surface needs refinement.

## 11. Molecule Surface Architecture Principle
Molecule experiences should be split by purpose:
- **Workspace**: short day-to-day cockpit
- **Results**: molecule-first ELN review
- **Sequence**: sequence/annotation/design context
- **Governance**: DI lineage, policy, and audit detail

Default molecule entry should be Workspace. Results/Sequence/Governance should remain one click away via persistent local navigation.
