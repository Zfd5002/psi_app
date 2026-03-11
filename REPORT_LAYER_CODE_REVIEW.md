# REPORT_LAYER_CODE_REVIEW

## Executive Summary
What is solid:
- Report payload construction is strongly contract-bound in `report_engine` via fixed section sets and validation (`validate_report_payload`), which reduces silent schema drift.
- Canonical serialization and fingerprinting are deterministic (`canonical_report_json`, `_compute_report_fingerprint`) and covered by tests.
- Report orchestration and web routing are separated cleanly: `reports_v3` assembles detail context; router maps report types to narrative renderers.
- Board/technical split is explicit in templates (`detail.html` + `_board_narrative.html` + `_technical_audit.html`) and print/PDF behavior is intentionally scoped.

What is risky:
- Some board templates intentionally drop structured determination fields and render placeholders (rule/snapshot/measurement), which can make board output appear less complete than payload content.
- Narrative extraction still depends on section-specific keys that differ across report types; this is a recurring source of "not assessed"/"none" fallbacks when payload shape evolves.
- `reports/new.html` guided selectors rely on JS; server-side parsing remains authoritative but UX can drift from server constraints if selector logic diverges.

---

## Architecture Evaluation

### Boundary quality (engine vs orchestration vs narrative vs templates)
- Engine (`psi/services/report_engine.py`):
  - Correctly owns report payload semantics and deterministic object formation (e.g., `build_report_payload`, `generate_*_report_v0`).
  - Determinism controls: sorted keys/sets, canonical JSON, explicit ordered rows.
- Orchestration (`psi/services/reports_v3.py`):
  - Correctly owns form parsing, policy pin construction, detail-context aggregation, and identity-summary derivation.
  - Includes deterministic enrichment for UI context (`rule_ids`, `measurement_key_citations`, `evidence_snapshot_refs`).
- Narrative (`psi/services/v3_narrative.py`):
  - Pure derived layer; does not persist or mutate payload.
  - Performs sanitization and display-only truncation.
- Templates/CSS (`psi/web/templates/reports/*`, `psi/web/static/style.css`):
  - Mostly presentational, with board/technical split and PDF-mode handling.
  - Some card rendering currently uses hard-coded placeholders instead of payload-provided citations.

### Where determinism is enforced
- Canonicalization and stable JSON: `report_engine.py` (`_canonicalize_report_obj`, `canonical_report_json`, `_compute_report_fingerprint`).
- Stable row ordering for comparative sets: `_order_molecule_comparative_rows`, `_order_program_comparative_rows`.
- Stable policy pin shape/order: `reports_v3.py:get_v3_report_policy_pins` returns sorted keys.
- Narrative list determinism: `v3_narrative.py` uses explicit list construction and `_display_limited` constant.
- Tests reinforce this: `tests/test_v3_report_engine_contracts.py`, `tests/test_v3_report_contracts.py`, `tests/test_v3_narrative_rendering.py`.

### Where determinism could drift
- Template-level rendering that bypasses structured fields and injects fixed placeholders (e.g., determination cards in `_board_narrative.html`).
- Divergence between `snapshot_coverage` in metadata and cited snapshot IDs in `reproducibility_appendix` can produce inconsistent snapshot messaging if consumers assume one source of truth.
- UI selector logic in JS can diverge from backend parsing behavior over time (ordering and cardinality still enforced server-side, but board UX consistency can drift).

### Most fragile schema/payload wiring points
- Cross-type identity derivation (molecule/program/comparative) in `reports_v3.py:build_report_identity_summary`.
- Narrative determination extraction fallbacks in `v3_narrative.py` (`_comparability_det`, `_posture_det`) due to different section locations by report type.
- Determination card wiring in `_board_narrative.html` currently does not pass structured `rule_id/snapshot_ids/measurement_keys` through.

---

## Potential Bug / Footgun List

1) Severity: High
- Location: `psi/web/templates/reports/_board_narrative.html` lines ~44-56 (determination card call)
- Failure mode:
  - Determination cards are rendered with hardcoded `rule_id="not_available"`, empty snapshot IDs, and empty measurement keys even when narrative payload includes these details in `det.details`.
- Likely symptom:
  - Board view determination cards show "Policy rule: missing"/"None" while technical view contains citations; perceived data loss.
- Suggested fix (do not implement here):
  - Extend narrative determination objects with explicit fields (`rule_id`, `snapshot_ids`, `measurement_keys`, `missing_inputs`) and pass them directly into `render_determination_card`.

2) Severity: Medium
- Location: `psi/services/v3_narrative.py` lines ~332-335 (`_comparison_narrative` next steps)
- Failure mode:
  - Comparison narratives read `experimental_gaps` as a flat string-list; comparative payloads often do not carry that section in meaningful form.
- Likely symptom:
  - "Next steps: None." even when other payload sections could support actionable board text.
- Suggested fix:
  - Define comparison-specific next-step extraction from sections that actually exist for comparative reports (or deterministic explicit "not provided by comparative schema" messaging).

3) Severity: Medium
- Location: `psi/services/report_engine.py` lines ~753 and ~824 (`catalog_versions.comparability_policy` hardcoded `v0.1` in comparative reports)
- Failure mode:
  - Comparative report reproducibility appendix can display a comparability policy version inconsistent with `reports_v3` policy pins (latest loader).
- Likely symptom:
  - Board/technical pages show conflicting policy versions for the same run context.
- Suggested fix:
  - Source comparability policy version uniformly from `load_comparability_policy_latest()` in all report generators.

4) Severity: Medium
- Location: `psi/services/reports_v3.py` lines ~201-206 (`generate_report_from_form`)
- Failure mode:
  - `subject_ids_text` parsing performs direct `int(x.strip())`; non-numeric token raises generic `ValueError` and returns broad HTTP 400.
- Likely symptom:
  - User sees low-quality validation feedback for malformed manual input.
- Suggested fix:
  - Add deterministic token-level validation and error message normalization before conversion.

5) Severity: Low
- Location: `psi/web/templates/reports/detail.html` lines ~17-24 and `_technical_audit.html` lines ~26-33
- Failure mode:
  - Executive header and technical payload labels are mixed report-specific terms (e.g., `molecule_report` marker key used for all report types by contract), which may confuse operators.
- Likely symptom:
  - Reviewers misread marker semantics as type-specific field mismatch.
- Suggested fix:
  - Keep required marker names for smoke contract, but add explicit explanatory label text nearby in template.

6) Severity: Low
- Location: `psi/web/templates/reports/new.html` JS logic lines ~107-225
- Failure mode:
  - Program/molecule option loading errors fall back to manual entry; UX is resilient but opaque for intermittent endpoint failures.
- Likely symptom:
  - Users see generic "Failed to initialize" and may assume data absence.
- Suggested fix:
  - Preserve deterministic behavior, but improve user-facing error granularity and ensure selector state reset is explicit.

7) Severity: Low
- Location: `psi/services/v3_narrative.py` `_clean_text` (lines ~29-38)
- Failure mode:
  - Aggressive punctuation normalization can alter certain scientific tokens/notations in edge cases.
- Likely symptom:
  - Minor display text deformation in board narrative (presentation only).
- Suggested fix:
  - Narrow normalization regex scope or gate it to sentence-like fields only.

---

## Testing Evaluation

What is covered well:
- Deterministic contracts and canonical serialization:
  - `tests/test_v3_report_engine_contracts.py`
  - `tests/test_v3_report_contracts.py`
- Identity summary derivation across report types and options endpoints ordering/filtering:
  - `tests/test_v3_reports_ui_identity.py`
- Narrative deterministic rendering and key fallbacks:
  - `tests/test_v3_narrative_rendering.py`

Missing/weak regression coverage (suggestions only):
- Board template rendering of determination cards should assert citations are surfaced when available (currently a likely gap).
- PDF-mode snapshot tests for major report types (or deterministic HTML fragment assertions) to catch layout regressions in `detail.html`/`style.css`.
- Cross-check test that `reproducibility_appendix.catalog_versions` aligns with policy pins for all report types.
- End-to-end test for `/reports/new` JS flow is hard in unit tests, but server-side validation tests for malformed `subject_ids_text` would reduce UX surprises.

---

## No-Go Zones (Must Remain Untouched in This Layer)
- DI semantics and policy outcome logic (`psi/services/di/*`, policy catalogs meaning).
- Snapshot contract and hash/fingerprint computation behavior.
- Replay behavior (`psi.tools.di_replay_regression`) and skip semantics.
- Ranking/shortlisting governance constraints (no weighted heuristics).

Presentation-layer work should remain derived-only and deterministic, with no mutation of persisted payload semantics.
