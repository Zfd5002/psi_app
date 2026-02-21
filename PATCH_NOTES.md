## 2026-02-20 — v1.2.9k
- Snapshot Integrity (additive): embed deterministic `provenance.integrity` with `snapshot_content_hash` + `evidence_fingerprint`.
- Snapshot Content Hash: sha256 over stable JSON of {inputs minus machine-local debug fields (e.g. policy_path), outputs with provenance.integrity removed, evidence_ids}.
- Evidence Fingerprint: sha256 over stable JSON of sorted selected-evidence tuples (metric_key, measurement_id, qc_status, unit, comparator).
- Verification CLI: add `python -m psi.tools.verify_snapshot --snapshot-id <id>` (read-only) to recompute integrity fields and classify drift deterministically.
- Drift Classification: emits one of {VERIFIED, POLICY_DRIFT, DATA_DRIFT, QC_DRIFT, STRUCTURAL_DRIFT} with explainable booleans.
- DI runner refactor (governance-only): split into pure `compute_di_output(...)` + persistence wrapper `run_di(...)` to support read-only verification.
- Docs: update `docs/DI_SNAPSHOT_CONTRACT.md` to define integrity fields and hashing rules.
- No DB changes. No migrations. No selector/gate/policy behavior changes.

## 2026-02-20 — v1.2.9j
- DI Governance Diagnostics: add deterministic evidence comparability + QC coherence reporting (no scoring; no gate behavior changes).
- DI Outputs (additive): new top-level `comparability` object with `metric_level[]`, `qc_coherence[]`, and summary counts (always emitted; deterministic ordering).
- DI Outputs (additive): new `confidence_degradation` object triggered only by high-severity comparability flags (structured reasons; no ranking).
- Readiness integration (additive): comparability may append to `readiness.assumptions`; policy may optionally treat certain high-severity comparability issues as `blocking_reasons` via `comparability_rules` (warn|block). Gates remain unchanged.
- Guardrails: extend `python -m psi.tools.di_contract_smoke` to assert comparability + confidence degradation presence and deterministic ordering.
- Docs: update `docs/DI_SNAPSHOT_CONTRACT.md` to define comparability + confidence degradation schema and determinism requirements.
- No DB changes. No migrations. Local-first. Overlay-safe.

## 2026-02-20 — v1.2.9i
- Maintenance + Formalization: resolve documentation drift (PSI_CONTEXT version invariants; DI snapshot contract aligned to current outputs).
- DI runner structure: soft-refactor internal module split under `psi/services/di/` (selection/eval/enrich) with orchestrator-only `runner.py` (no selection/gate evaluation behavior changes).
- Determinism guardrails: extend existing `python -m psi.tools.di_contract_smoke` to assert SoE v0.3 presence + readiness shape normalization + stable ordering.
- DI Outputs (additive): add `state_of_evidence.soe_v0_3` (schema_version="0.3") with deterministic `evidence_summary` by metric_key.
- DI Outputs (additive): readiness now includes normalized fields (`decision_context`, `readiness_level`, `blocking_gates`, `blocking_reasons`, `assumptions`, `required_next_steps`) while preserving existing readiness keys.
- DI Outputs (additive): add policy-derived `suggestions` list (non-ranked; deterministic) derived only from missing evidence / method/unit incompatibilities.
- Snapshot metadata (additive): outputs now include `engine.code_version` (from `psi/version.py`) and `engine.evaluation_version` alias for back-compat.
- Policy governance: enforce allowed policy package schema versions; unknown schema emits deterministic NOT_READY snapshot with clear error (instead of raising).
- No destructive DB changes. Local-first. Overlay-safe.

## 2026-02-20 — v1.2.9h1
- Release: permanent canonical version source at `psi/version.py`.
- App: UI footer + smoke tests now import `PSI_VERSION` from `psi.version` (no scattered literals).
- Tools: add `python -m psi.tools.print_version` as the stable verification entrypoint.
- Packaging: `compress.sh` now auto-detects version from `psi/version.py`.
- No DB changes. No migrations changes. No DI/selector/gate/policy behavior changes.

## 2026-02-20 — v1.2.9h
- DI Snapshot Diff (Roadmap v0.2): add `python -m psi.tools.di_snapshot_diff --id1 <id> --id2 <id>` to compute a deterministic, explainable diff between two DI DecisionSnapshots (read-only; no DB mutation).
- Drift diagnostics: tool emits a derived-only drift label in {no_change,data_drift,qc_drift,policy_drift,structural_drift} based only on embedded snapshot signals (hashes, identifiers, readiness/gates/QC fields).
- Guardrails: extend `python -m psi.tools.di_contract_smoke` to assert that diffing two deterministic reruns yields `no_change` and an empty change set.
- Docs: embed DI Mission & Roadmap at `docs/DI_MISSION_AND_ROADMAP.docx` and reference it from `PSI_CONTEXT.md` so future code-only ZIPs include it automatically.
- No DB changes. No migrations changes. No selector/gate/policy behavior changes.

## 2026-02-20 — v1.2.9g
- DI Readiness Formalization (Roadmap v0.2): add first-class `readiness` object to DI output (derived-only; no selector/gate/policy behavior changes).
- Gate Outcome Normalization (reporting-only): add `gate_outcomes` map with per-gate status + required/present/missing metric lists (sorted deterministically).
- Risk Flags (additive): add `risk_flags_enriched` with conservative category/severity/related_metrics fields (legacy `risk_flags` unchanged).
- Coverage fingerprinting: add `coverage_fingerprint` (sha256 over stable JSON of blockers + coverage counts/ratio + gate_outcomes + comparability; excludes runtime-only values).
- Guardrails: extend `python -m psi.tools.di_contract_smoke` to assert readiness presence, deterministic ordering, and stable coverage_fingerprint.
- No DB changes. No migrations changes.

## 2026-02-20 — v1.2.9f1
- Hotfix: repair `psi/tools/di_contract_smoke.py` (IndentationError) and restore contract smoke execution.
- Determinism harness: assert determinism over the DI output payload (excluding DB-assigned `snapshot_id`, which must vary per run because a new DecisionSnapshot row is inserted).
- No DI behavior changes, no selector/gate changes, and no DB changes.

## 2026-02-20 — v1.2.9f
- DI State of Evidence: add additive `state_of_evidence.soe_v0_2` (descriptive only; no behavior change).
- SoE v0.2 includes: requirements derived from policy gates, per-metric status (including "present via alias" explanation), per-gate coverage checklist, deterministic summary counts, QC summary (reuse existing QC semantics), and recency reporting (produced_at fallback to created_at; no thresholds).
- Alias semantics: unchanged; existing policy `metric_alias_map` behavior is preserved and now explicitly explained in SoE output.
- Guardrails: extend `python -m psi.tools.di_contract_smoke` to validate SoE v0.2 presence, key ordering determinism, allowed status enums, and snapshot determinism.
- No DB changes.

## 2026-02-20 — v1.2.9e
- DI Constitution: add `docs/DI_CONSTITUTION.md` (v0.1 lock-in) documenting determinism, policy packaging, template ontology, selection semantics versioning, ignore taxonomy, and drift guards.
- DI Policy Package: `advance_to_in_vivo_v0_1.json` now declares `template_structure` (ontology declaration) without changing evaluation semantics.
- DI Selection Semantics: snapshots now emit `selection_semantics_version = di.selection.v0_1` in provenance + inputs.
- Guardrails: harden `python -m psi.tools.di_contract_smoke` to validate ontology presence, selection semantics version, blocker taxonomy membership, and experiment suggestion integrity (sorted/deduped; keys exist in catalog).
- No DB changes.

## 2026-02-20 — v1.2.9d
- DI Policy Packaging (dual-hash): policies are structured packages with both a semantics hash (policy_body) and an integrity hash (full package).
- DI Snapshots: inputs_json includes policy_id/version/name/schema_version + policy_semantics_hash + policy_package_hash (additive only; policy_json_canonical retained).
- DI UI: snapshot viewer shows policy_id/version + semantics hash + collapsible package hash + collapsible changelog.
- DI Compare: distinguishes semantic policy changes vs metadata-only changes.
- DI Experiment Catalog v0: add referenced experiment catalog (catalog_id/version/hash; catalog JSON not embedded in snapshots).
- DI Outputs: add neutral blocker → experiment mapping (`experiment_suggestions`) with UI label "Experiments that address this blocker".
- DI Ignored Evidence Taxonomy: selectors emit stable reason_key values with deterministic ordering; UI groups ignored evidence by reason_key.
- Docs: update DI snapshot contract for policy packaging, catalog refs, and ignore taxonomy.
- Guardrails: extend di_contract_smoke to validate dual-hash stability, catalog hash, and ignore reason key set.

## 2026-02-20 — v1.2.9c
- DI UI: dedicated DI snapshot viewer with gates/blockers/risk flags/provenance panels and an evidence table (read-only, snapshot-driven).
- Decisions: add snapshot JSON export endpoint and UI button (local-first audit artifact).
- Decisions: add DI snapshot compare page (DI-only) highlighting changes in policy hash, evidence set, gates, blockers, risk flags, and provenance.
- Docs: add DI snapshot contract specification (docs/DI_SNAPSHOT_CONTRACT.md).
- Guardrails: add lightweight DI contract smoke tool (python -m psi.tools.di_contract_smoke).

## 2026-02-20 — v1.2.9b
- DI snapshot contract hardening:
  - Snapshots embed canonical policy JSON (`policy_json_canonical`) + policy_source + policy_hash for snapshot-alone reproducibility.
  - Snapshot rows are schema-discriminated via nullable `engine_key` and `schema_version` (DI vs legacy).
  - Snapshots record engine/selector/evaluator/schema identifiers for provenance and auditability.
- UI: /decisions now renders both legacy rule-engine snapshots and DI snapshots safely (no schema collisions).
- Determinism: snapshot JSON serialization remains stable; DI evidence list explicitly labeled `measurement_ids_used`.

## 2026-02-19 — v1.2.8c
- Hotfix: smoke_test PATCH_NOTES guardrail now treats the topmost dated entry as the latest (PATCH_NOTES is newest-first).

## 2026-02-19 — v1.2.8a
- Hotfix: wide exporter no longer crashes when enriching measurement rows (convert SQLAlchemy RowMapping to dict before attaching QC fields).

## v1.2.5b
- Hotfix: fix indentation bug in export_wide QC attach block (SyntaxError return outside function).
- Hotfix: ensure scripts/start_psi.sh is executable in overlays.

# PSI Patch Notes (append-only)


## 2026-02-19 — v1.2.5a
- QC & Governance foundation:
  - New append-only QC event log for measurements (`measurement_qc_events`) with reviewer attribution.
  - Latest-state QC cache (`measurement_qc`) for fast UI badges.
  - Data record detail: show extracted measurements and allow minimal QC review actions.
  - Molecule batch panels: show per-batch QC counts (pending/rejected/quarantined).
- Exporter: `psi/scripts/export_wide.py` supports `--qc-mode none|model_safe|strict` (default `none`).


## 2026-02-18 — v1.2.3f
- UI (molecule detail): add Data Overview (counts + lightweight aggregates) and show batch header headline results.
- UI (molecule detail): move unbatched records into a final “Unassigned” batch panel (batch-first everywhere).
- Deterministic ordering for batch panels and run lists; null-safe rendering and JS (no migrations).

## 2026-02-18 — v1.2.1
- Improved molecule detail readability with collapsible computed run history and run log.
- Continued standardization of experiment inputs/results to support safer downstream tooling.

## 2026-02-18 — v1.2.3c
- Stabilized measurement extraction + storage and centralized "primary measurement" selection.
- Added explicit, env-gated CSV export (with filters + wide-ish primary_* columns).
- Added CLI-only backfill + QC tools (SAFE defaults; idempotent behavior).
- Added localStorage remember-state for run history/log collapsibles.

## 2026-02-18 — v1.2.3d
- Packaging: harden overlay ZIP exclusions (vendor/caches)
- Release: add bump_version helper + smoke_test guardrail
- UI: molecule-scoped <details> persistence + batch expand/collapse

## 2026-02-18 — v1.2.3e
- Measurements: formalize schema-tolerant inserts (PRAGMA-driven, per-DB cache, conservative NOT NULL fallbacks)
- Measurements: add internal self-check to prevent mismatched insert columns/binds
- Smoke test: add compatibility matrix for alternate measurement schemas (numeric-only, text-only, deterministic primary)
- Export: deterministic ordering when data_records.created_at is NULL
- Packaging: exclude editor/backup artifacts from overlay ZIPs

## 2026-02-18 — v1.2.3f
- UI: Molecule detail is batch-first with a Data Overview summary and expandable batch panels showing headline results.
- Deterministic ordering for batches and records; unbatched records appear under an Unassigned panel.
- No migrations.

## 2026-02-19 — v1.2.3g
- Measurements: introduce export-first measurement registry (canonical keys, aliases, deterministic export naming).
- Export: add deterministic registry-driven wide/pivot CSV exporter (CLI: python -m psi.scripts.export_wide).
- Measurements: add additive per-measurement provenance columns on data_measurements (producer, producer_version, source_path, run_id, produced_at, notes).
- Packaging: rsync overlay now excludes vendor/ (ANARCI rehydrate stays via scripts/install_anarci.sh); docs updated.

## 2026-02-19 — v1.2.3g1
- Hotfix: ensure `data_measurements` table exists for fresh DBs (smoke_test + measurement upsert).
- Hotfix: overlay apply script no longer uses rsync --delete (prevents accidental deletion of local-only paths like vendor/).

## 2026-02-19 — v1.2.3g2
- Measurement system evolution (export-ready): schema-driven registry + deterministic wide exporter + per-measurement provenance (additive, backward compatible).
- Overlay workflow hardening: apply script no longer deletes local-only directories; safer rsync behavior.

## 2026-02-19 — v1.2.4a
- Export: --as-of leakage-safe wide export + ignore_for_model QC flag
- DecisionSnapshot: add as_of_ts + notes; add OutcomeLabel table for supervised outcomes
- Release: bump_version helper can update footer version automatically

## v1.2.5a (2026-02-19)
- Hotfix: fix SyntaxError in export_wide QC filtering block (indentation / continue outside loop).

## 2026-02-19 — v1.2.6
- Raw File Registry & Provenance foundation:
  - Files: add provenance metadata columns (source_kind, source_path, collected_at, imported_at, instrument, operator, run_id, tags_json, notes).
  - File links: add typed link roles + optional label (raw_input, processed_output, report, plot, protocol, other).
  - Provenance graph: introduce file_derivations (parent→child) with optional transform/tool metadata.
  - UI: add /files registry page with basic search + source_kind/sha prefix filters and deterministic ordering.
  - UI: attachment lists display role badges; key upload forms capture role + provenance fields.
  - CLI: add import-from-path helper (python -m psi.scripts.import_file) to register and link local raw files.

## 2026-02-19 — v1.2.7
- Molecule detail (batch-first): add QC selection mode toggle (All / Model-safe / Approved-only) that affects batch headline metric selection.
- Molecule detail: show minimal per-run QC badges in batch tables when runs contain pending/rejected/quarantined measurements.
- Performance: avoid per-batch measurement count queries by computing counts in a single grouped query.

## 2026-02-19 — v1.2.8
- Export (wide): add named, deterministic export profiles (`--profile ML_core|CMC_only|Binding_only`) with profile-specific default QC modes.
  - Defaults apply only when a profile is selected; explicit `--qc-mode` always wins.
- Export (wide): fix default `qc_mode=none` runtime bug and centralize measurement table reflection/ensure logic to reduce drift.
- Core: introduce `psi/core/measurement_schema.py` as canonical data_measurements schema/reflection helper.
- Smoke test: now exercises the registry-driven wide exporter (default + profile) to prevent regressions.

## 2026-02-20 — v1.2.9a
- DI (Decision Intelligence) v0.1 (headless): introduce policy-as-data JSON + stable hashing, deterministic batch-first evidence selection, gate/blocker evaluation for `advance_to_in_vivo`, and snapshot persistence to `decision_snapshots` via CLI.
- DI: adds `python -m psi.tools.run_di` to print deterministic JSON to stdout and write a DecisionSnapshot row without mutating measurements/QC.
