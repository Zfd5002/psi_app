# Scientific Claims & Hypothesis Layer

Version: v1.3.0c90

## What a Claim Is

A scientific claim is a structured assertion PSI is trying to evaluate, such as:
- Molecule is suitable to advance to in vivo.
- Variant improves internalization without unacceptable affinity loss.
- Molecule developability is consistent with screening expectations.

Claims are not raw evidence and not task records.

## What a Hypothesis Is

A hypothesis is an early-stage claim state (`hypothesis`) with insufficient support.

Recommended lifecycle:
- `hypothesis` -> `emerging`
- `emerging` -> `supported` or `contradicted`
- `supported`/`contradicted` -> `archived`

Transitions are deterministic and one-way by default.

## Data Model

Core entity:
- `ScientificClaim`

Link entities:
- `ScientificClaimEvidenceLink` (DataRecord linkage with direction)
- `ScientificClaimDecisionLink` (DecisionSnapshot linkage)
- `ScientificClaimTaskLink` (ExperimentTask linkage)

## Relation to Existing PSI Layers

Claims connect existing read/write systems without mutating them:
- Evidence/DataRecord: support or contradiction signals
- DI DecisionSnapshot: linked context only
- ExperimentTask: linked testing/de-risking work only
- Trajectory: relevant projected next experiments for a claim

## Architectural Boundaries

This layer must not:
- modify DI semantics
- write into snapshot payloads
- create hypothetical DataRecord rows
- mutate task state during claim reads/summaries

Claims are an additive semantic layer.

## Scientist Surfaces

- Molecule detail: top active claims with support/conflict and maturity context
- Claim detail: linked evidence, decisions, tasks, maturity summary, relevant trajectory candidates
- Program detail: claim rollups and top claims
- Portfolio overview: claim insight buckets (supported, at-risk, evidence-starved, task burden)

## Future Extension Points

- claim review workflows
- claim dispute resolution metadata
- policy-linked claim taxonomies
- claim lineage across variants/program phases
