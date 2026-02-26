# CODE REVIEW w83 (w75-w82)

## Scope Reviewed

Patches reviewed:

- `v1.2.9w75` error-output parity hardening (governance/run-semantics parity)
- `v1.2.9w76` template prerequisites catalog coverage + deterministic latest loader
- `v1.2.9w77` scientist-header prerequisite advisory (UI-only impossible-state prevention)
- `v1.2.9w78` heavy compute OFF-by-default helper + UI indicator
- `v1.2.9w79` confidence model audit (non-weighted, neutral missing evidence)
- `v1.2.9w80` deterministic sorting audit for molecule-header advisory lists
- `v1.2.9w81` deterministic read-only outcome dataset export groundwork
- `v1.2.9w82` operator notes documentation

## Summary

No functional determinism/replay regressions were identified in the reviewed patches.

The chain remains aligned with the stated constraints:

- Deterministic ordering enforced/expanded in UI advisory and confidence surfaces
- Replay safety preserved (error-output parity remains extension-gated for new snapshots only)
- Policy-as-data strengthened (template prerequisites latest-loader + coverage audit)
- UI-only features (prerequisite advisories, heavy-compute indicators, confidence bar) remain out of DI hash-bearing outputs
- No schema changes introduced in w75-w82

## Risks Found

None found (functional determinism/replay/hash-safety risks).

## Proof Notes (Gates + Replay)

For each patch `w75` through `w82`, the required gate suite was run and passed:

- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

Replay regression remained read-only (`ensure=False`) and passed on the latest 5 matched snapshots for each patch step.

## Patch-by-Patch Review Notes

### w75 (error-output parity hardening)

- Error-output parity completion remains additive and gated by `error_output_parity_v2_0a`.
- Contract smoke now selects a parity-gated representative snapshot (avoids false coverage from older ungated snapshots).
- `value_functions_enforcement_reason` presence is checked on both success and synthesized error outputs under the applicable gate.

### w76 (template prerequisites catalog coverage)

- Deterministic `load_template_prerequisites_latest()` implemented (version tuple + filename tie-break).
- Molecule header now loads template prerequisites via latest loader (current behavior unchanged with only `v0_1` present).
- Contract smoke cross-checks `progress_policy_v0_1` DI milestone template keys against template-prereq coverage.

### w77 (UI-only impossible progress advisory)

- Molecule header advisory classifies prerequisite blockers as `missing` vs `failed`.
- Advisory explanation text is plain-English and explicitly states `Blocked by prerequisites`.
- Logic remains UI/view-model only; no DI compute changes.

### w78 (heavy compute guard)

- Global helper centralizes `PSI_HEAVY_COMPUTE` interpretation with OFF-by-default behavior.
- UI surfaces (molecule header and `/di/run`) clearly show OFF/ON and state hash non-impact.
- No DI snapshot hash-bearing fields changed.

### w79 (confidence model audit)

- Confidence logic remains count-based and non-weighted.
- `not_assessed` components remain neutral and are not counted as concerns.
- Contract smoke locks component order and rule-text non-weighted wording.

### w80 (determinism hygiene)

- Explicit sorting added for prerequisite status rows, blocked prerequisite rows, and advisory rows.
- Small helper makes blocker ordering rule explicit and testable.
- Contract smoke asserts blocker ordering determinism independent of input order.

### w81 (outcome dataset export groundwork)

- New tool is read-only and deterministic (`snapshot_id` ascending JSONL + stable JSON serialization).
- Uses existing DB fields only (no schema changes, no writes).
- Aggregates outcome labels in deterministic order and surfaces DI review labels when present.

### w82 (operator notes docs)

- Documentation-only patch.
- Notes are consistent with current catalog loaders, risk mapping, enforcement reason enum semantics, and heavy-compute helper/UI semantics.

## Follow-on Fix List (if needed)

None at this checkpoint.
