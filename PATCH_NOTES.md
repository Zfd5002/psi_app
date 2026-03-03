## 2026-03-02 — v1.3.0a90
Why:
- Improve board-first PDF export readability and print stability without changing report semantics.

What:
- Added print/PDF presentation polish in `psi/web/static/style.css`:
  - break-avoid rules for key report blocks/cards/lists,
  - improved wrap behavior for table and long text content,
  - normalized print/PDF typography and spacing.
- Added minimal report-template wrapper classes for targeted styling:
  - `psi/web/templates/reports/detail.html`
  - `psi/web/templates/reports/_board_narrative.html`
- No changes to report ordering, payloads, routing, or logic.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/style.css`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_board_narrative.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- Presentation-only patch.
- No DI semantic/policy/ranking/hashing/replay changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a89
Why:
- Complete removal of the legacy compatibility shim for `v3_board_reports` so only the quarantined deprecated module remains.

What:
- Deleted `psi/services/v3_board_reports.py` (legacy shim removed).
- Confirmed legacy skipped tests remain skip-only and do not import the removed shim at module import time:
  - `tests/test_v3_board_report_rendering.py`
  - `tests/test_v3_molecule_report_schema.py`
  - `tests/test_v3_board_report_determinism.py`
  - `tests/test_v3_executive_summary_bullets.py`
  - `tests/test_v3_comparison_report_schema.py`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py` (deleted)

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic/policy/ranking/hashing/replay behavior changes.
- No DB schema/migration changes.

## 2026-03-02 — v1.3.0a88
Why:
- Resolve maintenance ambiguity from parallel “board report” code paths by quarantining the orphan path that is not router-wired in V3 runtime surfaces.

What:
- Quarantined legacy board report implementation under:
  - `psi/services/_deprecated/v3_board_reports.py`
  - `psi/services/_deprecated/__init__.py`
- Added compatibility shim at `psi/services/v3_board_reports.py` with explicit deprecation header; no live router wiring added/changed.
- Retired orphan-only pytest modules by replacing them with explicit deterministic skips:
  - `tests/test_v3_board_report_determinism.py`
  - `tests/test_v3_board_report_rendering.py`
  - `tests/test_v3_molecule_report_schema.py`
  - `tests/test_v3_comparison_report_schema.py`
  - `tests/test_v3_executive_summary_bullets.py`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `psi/services/_deprecated/__init__.py`
- `psi/services/_deprecated/v3_board_reports.py`
- `tests/test_v3_board_report_determinism.py`
- `tests/test_v3_board_report_rendering.py`
- `tests/test_v3_molecule_report_schema.py`
- `tests/test_v3_comparison_report_schema.py`
- `tests/test_v3_executive_summary_bullets.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Live routes unchanged.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a87
Why:
- Report policy pin bundle referenced comparability catalog `v0.1` while report generators already use `load_comparability_policy_latest()` (currently `v0.2`), causing audit-surface mismatch.

What:
- Updated `get_v3_report_policy_pins()` in `psi/services/reports_v3.py` to source comparability pins from `load_comparability_policy_latest()`.
- Added deterministic test in `tests/test_v3_report_engine_contracts.py` asserting pinned comparability `policy_id` and `policy_version` match the latest loaded policy.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `tests/test_v3_report_engine_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a86
Why:
- Program narrative next-steps wiring incorrectly read `experimental_gaps` instead of program report `next_best_experiments.items`.

What:
- Updated `render_program_narrative()` in `psi/services/v3_narrative.py` to derive next steps from `sections.next_best_experiments.items`.
- Added deterministic rendering fallback order per item:
  - `label`
  - `suggestion_key`
  - stable stringified fallback.
- Added unit test in `tests/test_v3_narrative_rendering.py` asserting stable, non-empty next-step extraction from `next_best_experiments.items`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a85
Why:
- Remove unreachable/dead code in program comparative report generator to reduce maintenance ambiguity and prevent accidental future misuse.

What:
- Deleted dead block after `return persist_report_run(...)` in `generate_program_comparative_report_v0()` within `psi/services/report_engine.py`.
- No behavioral changes; function return path and payload logic remain identical.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a84
Why:
- Program narrative headline/program label could fall back to `unidentified program` because program reports typically store identity under `sections.metadata`, not `identity_context`.

What:
- Updated `render_program_narrative()` in `psi/services/v3_narrative.py` to use deterministic fallback order:
  - `sections.identity_context.program_name`
  - `sections.metadata.program_name`
  - `sections.identity_context.program_id`
  - `sections.metadata.program_id`
  - `unidentified program`
- Program status row now emits `program_id=<id>` when name is unavailable.
- Added deterministic unit test in `tests/test_v3_narrative_rendering.py` for metadata-based program identity fallback.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a83
Why:
- Ensure board/narrative measurement summaries reflect present `used_by_metric` evidence instead of appearing empty.

What:
- Added deterministic `measurement_keys` wiring to molecule report reproducibility appendix from `used_by_metric` keys (sorted).
- Added deterministic program report `measurement_keys` wiring as sorted union of:
  - measurement keys from latest included molecule snapshots (`used_by_metric`)
  - comparability cited measurement keys already present in program comparability rows.
- Added deterministic contract assertions in `tests/test_v3_report_contracts.py` for molecule/program reproducibility `measurement_keys`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic changes.
- No DB schema/migration changes.
- Replay invariance preserved.

## 2026-03-02 — v1.3.0a82
Why:
- Fix brittle comparative report identity rendering by moving board-facing identity derivation into deterministic Python context assembly.
- Add print/PDF export mode for report detail pages with stable board-first layout.
- Replace raw-ID report generation UX with guided deterministic selectors while preserving manual-ID fallback.

What:
- Server-derived identity summary (Option B) added in `psi/services/reports_v3.py`:
  - New `build_report_identity_summary(...)` used by `get_report_run_detail(...)`.
  - Deterministic identity formatting for `molecule_report`, `program_report`, `molecule_comparative_report`, and `program_comparative_report`.
  - Comparative identity uses `molecule_set.rows` / `program_set.rows` stable row order.
  - Board identity text filters 64-hex hash tokens.
- Report detail route/template PDF mode:
  - `GET /reports/{id}?export=pdf` sets `is_pdf` and `body_class="pdf-mode"`.
  - Board View remains default; in PDF mode tabs and technical pane are suppressed.
  - Added deterministic “Export PDF” link in normal mode.
- Guided report generation form:
  - New JSON endpoints:
    - `GET /reports/options/programs`
    - `GET /reports/options/molecules?program_id=...`
  - `reports/new.html` now uses dependent selectors:
    - program selector for program report types,
    - program then molecule selector for molecule report types.
  - Comparative selection validation enforces 2–5 picks in UI and server-side form parser.
  - Manual IDs path retained behind toggle for graceful degradation.
- Added deterministic tests:
  - `tests/test_v3_reports_ui_identity.py`
    - identity summary derivation coverage
    - options endpoints ordering/filter behavior.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/new.html`
- `psi/web/templates/base.html`
- `psi/web/static/style.css`
- `tests/test_v3_reports_ui_identity.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

Guarantees:
- No DI semantic/policy/ranking/replay logic changes.
- No DB schema/migration changes.
- Deterministic ordering preserved.

Rsync overlay instructions:
- `rsync -av --no-times ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a82_<timestamp>/ /home/zach/psi_repo/`

## 2026-03-02 — v1.3.0a81
Why:
- Fix board readability regressions where report identity and subjects could render as `missing`/`Not yet captured` despite available payload data.

What:
- Updated `reports/detail.html` Executive Header identity rendering (template-only):
  - Added deterministic `identity_summary` for all report types.
  - Uses `identity_context` when present.
  - Falls back to `metadata` + `molecule_set.rows` / `program_set.rows` for comparative reports.
  - Avoids raw dict dumps in board identity display.
- Updated `psi/services/v3_narrative.py` (derived narrative layer only):
  - Molecule Stage now prefers `stage_determination.decision_state`, then `readiness_state`, then `Not assessed yet`.
  - Molecule Next steps now reads `experimental_gaps.blockers` first, then `experimental_gaps.next_best_experiments`, preserving payload order.
  - Comparative Subjects now derive from:
    - `molecule_set.rows` for molecule comparative
    - `program_set.rows` for program comparative
    with deterministic best-effort labels.
- Added deterministic regression tests in `tests/test_v3_narrative_rendering.py` for:
  - molecule stage precedence
  - molecule next-step extraction
  - molecule/program comparative subjects derivation from row sets.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (matched=5 failed=0 skipped=0)

Guarantees:
- No DI semantic changes.
- No DB changes.
- Replay invariance preserved.

Rsync overlay instructions:
- `rsync -av --no-times ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a81_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a80
Why:
- Final board-readability consistency and accessibility pass across report/lineage toggles and section framing.

What:
- Added minimal presentational accessibility improvements:
  - active button visual state (`.btn.active`)
  - consistent technical-panel separator styling (`.technical-panel`)
- Updated Board/Technical toggle controls across report and lineage templates to include `aria-controls` and stable panel IDs.
- Ensured non-JS fallback remains readable: Board and Technical sections are both visible and clearly separated.
- Kept headings and panel framing consistent across:
  - `reports/detail.html`
  - `reports/board_upgrade_delta_v3.html`
  - `reports/board_template_ladder_v3.html`
  - `lineage/program_detail.html`
  - `lineage/portfolio_detail.html`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/static/style.css`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a80_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a79
Why:
- Reduce hash/canonical-noise in board-facing sections so executive readers see status and actions, while hashes remain available only in technical/audit views.

What:
- Updated `reports/detail.html` board header to remove direct fingerprint display from Board View.
- Updated `reports/board_upgrade_delta_v3.html`:
  - Board View now shows only `changed_key_count` from header.
  - Full header (including hash fields) moved to Technical View.
- Updated lineage board sections to avoid raw event-object dumping and show compact deterministic count bullets instead.
- Added regression coverage in `tests/test_v3_narrative_rendering.py` to assert board narrative outputs do not contain 64-hex hash tokens.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a79_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a78
Why:
- Make determination cards board-readable with consistent human wording and deterministic missing-inputs language.

What:
- Updated shared determination card macro in `reports/_determination_card.html`:
  - Outcome labels now render in human-readable form (for example `not_assessed` -> `Not assessed yet`, `policy_disabled` -> `Not enabled`).
  - `Rule ID` label changed to `Policy rule` while preserving the same underlying value.
  - Snapshot section now shows `No snapshots captured yet` when `missing_inputs` exists and no snapshot IDs are cited.
  - Measurement keys now render as compact chips instead of JSON-like lists.
  - Missing inputs language standardized to:
    `This determination is not assessed until these inputs exist: ...`
- Presentation-only changes; determination payload semantics unchanged.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/_determination_card.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a78_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a77
Why:
- Move lineage program/portfolio pages to executive-first board mode while preserving full raw audit visibility in a secondary technical view.

What:
- Updated `lineage/program_detail.html`:
  - Added Board/Technical toggle (Board default).
  - Board section now shows compact executive summary counts and key lineage events.
  - Technical section collapses raw warnings/changes/rollups/history/membership JSON under `Show raw`.
- Updated `lineage/portfolio_detail.html`:
  - Added Board/Technical toggle (Board default).
  - Board section shows portfolio summary and key child-program lineage events.
  - Technical section collapses raw warnings/summaries/governance/membership JSON.
- Presentation-only changes; lineage semantics/data untouched.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a77_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a76
Why:
- Make upgrade delta and template ladder pages executive-first by default while preserving full technical audit surfaces behind an explicit toggle.

What:
- Updated `reports/board_upgrade_delta_v3.html`:
  - Added Board/Technical view toggle (Board default).
  - Board section now emphasizes `Executive Summary`, `What changed`, and `What’s required next`.
  - Technical section contains raw appendix JSON and reproducibility footer.
  - Preserved legacy literals required by tests: `Upgrade Delta Header`, `Change Table`.
- Updated `reports/board_template_ladder_v3.html`:
  - Added Board/Technical view toggle (Board default).
  - Board section emphasizes stage table and next actions.
  - Technical section contains raw missing prerequisite JSON and reproducibility footer.
  - Preserved legacy literals required by tests: `Template Ladder Header`, `Stage Table`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a76_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a75
Why:
- Complete deterministic narrative mapping coverage for all four report types with board-friendly subject labeling and clean empty-state phrasing.

What:
- Refined comparison narrative rendering in `psi/services/v3_narrative.py`:
  - Uses `II_general_profile.columns` to display board-friendly subjects (for example `M1 (Mol One)`).
  - Uses deterministic empty phrasing (`Not yet captured`, `None`) instead of array literals.
- Added tests in `tests/test_v3_narrative_rendering.py` to assert:
  - deterministic behavior across all report types,
  - friendly comparison labels,
  - no array-literal leakage in board narrative output.
- Existing report-type router mapping from `a74` continues to cover:
  - `molecule_report`
  - `program_report`
  - `molecule_comparative_report` / `molecule_comparison_report`
  - `program_comparative_report` / `program_comparison_report`

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a75_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a74
Why:
- Make board narrative the default report detail experience while preserving technical audit visibility and deterministic structured markers.

What:
- Updated `reports/detail.html` to default to Board View and provide a client-side Board/Technical toggle.
- Added `reports/_board_narrative.html` for executive-first narrative rendering (headline, status, determinations, evidence, next steps).
- Added `reports/_technical_audit.html` for secondary technical/audit content (pins, fingerprint metadata, warnings, raw payload).
- Wired router context to provide `board_narrative` using deterministic narrative renderers in `psi/services/v3_narrative.py`.
- Preserved required structured marker keys in rendered HTML:
  - `identity_context`, `molecule_report`, `policy_summary`, `rule_summary`, `measurement_summary`, `evidence_summary`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_board_narrative.html`
- `psi/web/templates/reports/_technical_audit.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a74_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a73
Why:
- Add a deterministic board narrative rendering layer that translates existing report payloads into executive-readable text without changing semantics or persisted JSON.

What:
- Added `psi/services/v3_narrative.py` with pure deterministic renderers:
  - `render_molecule_narrative`
  - `render_program_narrative`
  - `render_molecule_comparison_narrative`
  - `render_program_comparison_narrative`
- Narrative model includes stable keys/order: headline, status rows, what-this-means, evidence status, determinations, next steps, technical notes.
- Added sanitization to prevent hash-like 64-hex tokens in board narrative strings.
- Added deterministic tests in `tests/test_v3_narrative_rendering.py`.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_narrative.py`
- `tests/test_v3_narrative_rendering.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a73_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a72
Why:
- Normalize board packet page framing for upgrade delta, ladder, and lineage surfaces with consistent section titles and compact reproducibility footer style.

What:
- Updated templates for visual consistency and deterministic reading order:
  - `reports/board_upgrade_delta_v3.html`
  - `reports/board_template_ladder_v3.html`
  - `lineage/program_detail.html`
  - `lineage/portfolio_detail.html`
- Added “Show raw” collapsible blocks for long JSON sections (client-side `<details>` only).
- Added consistent “Reproducibility & Fingerprints” footer sections.
- Presentation-only changes; report payloads and semantics unchanged.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a72_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a71
Why:
- Make comparison report pages board-readable with consistent framing and explicit neutral handling when ranking is policy-disabled/incomplete.

What:
- Updated comparative report presentation in `reports/detail.html`:
  - Executive header now includes selected entity list for comparative reports
  - Added Comparison Highlights section
  - Determinations section now renders ranking as neutral `not_enabled` when policy is disabled/incomplete
  - Added required one-line governance note for disabled ranking:
    “Governance note: ranking is policy-controlled and currently disabled.”
- Presentation-only; no JSON/report semantics changed.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a71_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a70
Why:
- Improve program report readability by making posture interpretation and citations immediately visible to board readers.

What:
- Updated `reports/detail.html` for program reports:
  - Program posture determination card is now prominent directly under the executive header
  - Added static one-line “What this means” explanatory text under posture outcome
  - Added compact citation rendering for snapshot/template/decision references from rollup citations
- Presentation-only update; no report semantics changed.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a70_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a69
Why:
- Improve molecule report board readability with a clearer top-down flow and compact executive bullet framing.

What:
- Updated `reports/detail.html` presentation order for molecule reports:
  - Executive Summary bullets
  - Determinations
  - Evidence
  - Measurements
  - Rules & Policy
  - Reproducibility & Fingerprints
- Added client-side “Show all / Show less” toggle for executive bullets (first 5 shown by default).
- Label/heading wording adjusted for board-friendly readability only; underlying payload unchanged.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a69_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a68
Why:
- Improve board readability on report detail pages with a clear executive hierarchy and deterministic determination cards, without changing any report semantics.

What:
- Added reusable determination card macro partial:
  - `psi/web/templates/reports/_determination_card.html`
- Refactored `reports/detail.html` presentation:
  - Executive Header block at top
  - Determinations section with cards for comparability, program posture, and ranking status
  - standardized Rules & Policy / Evidence / Measurements / Reproducibility sections
  - preserved required structured markers (`identity_context`, `molecule_report`, `policy_summary`, `rule_summary`, `measurement_summary`, `evidence_summary`)
- No JSON/report payload logic changed; rendering only.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/reports/_determination_card.html`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a68_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a67
Why:
- Harden upgrade semantic-ack enforcement so semantic actions cannot bypass acknowledgment checks.

What:
- Added a single guard wrapper in `psi/services/policy_upgrade.py`:
  - `run_semantic_action_with_ack_guard(...)`
- Refactored semantic report entry points to route through the guard wrapper:
  - `psi/services/reports_v3.py::generate_report_from_form(...)`
  - `psi/services/report_engine.py::persist_report_run(...)`
- Added tests validating deterministic block/allow behavior:
  - unacknowledged semantic warning => raises `policy_upgrade_action_required`
  - acknowledged session => semantic action proceeds deterministically.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/services/reports_v3.py`
- `psi/services/report_engine.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a67_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a66
Why:
- Remove governance ambiguity around hardcoded ordering by making internal deterministic tie-break behavior explicit, locked, and documented as a narrow non-heuristic exemption.

What:
- Added explicit shortlisting internal tie-break constant:
  - `SHORTLISTING_INTERNAL_TIEBREAK_KEYS`
- Refactored shortlisting sort tuple assembly to consume the explicit constant list.
- Added governance note doc:
  - `docs/DI_V3_GOVERNANCE_NOTES.md`
- Added lock tests asserting exact tie-break key literal list and no weighted token reintroduction.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/shortlisting.py`
- `docs/DI_V3_GOVERNANCE_NOTES.md`
- `tests/test_shortlisting_tiebreak_governance.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a66_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a65
Why:
- Enrich program rollup posture semantics with explicit policy-order rules and citations, without introducing any numeric scoring or weighted heuristics.

What:
- Added additive `program_rollup_policy_v0_1.json` with ordered posture states and ordered rule precedence.
- Refactored rollup posture derivation in `psi/services/program_rollups.py` to policy-order evaluation with explicit citations:
  - `posture_state`, `rule_id`, `cited_snapshot_ids`, `cited_templates`, `cited_decisions`, `rationale`, `notes`
- Wired posture object into program report sections and lineage summary surfaces.
- Added deterministic tests for policy loading/ordering and posture payload constraints, including banned-key assertions (`score`, `weight`, `points`, `ranking_score`, `numeric_total` absent).

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/program_rollup_policy_v0_1.json`
- `psi/services/program_rollups.py`
- `psi/services/report_engine.py`
- `psi/services/lineage.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_program_rollup_posture_policy.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a65_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a64
Why:
- Elevate comparability semantics to governance-grade deterministic determination objects with explicit rule/citation surfaces and policy-order precedence.

What:
- Added additive `comparability_policy_v0_2.json` with ordered categorical rules and deterministic rationale fragments.
- Implemented validated comparability policy latest-loader and full determination builder in `psi/services/comparability.py`:
  - always returns `category`, `rule_id`, `measurement_keys`, `snapshot_ids`, `rationale`, `notes`
  - deterministic downgrade to `category=not_assessed` + `rule_id=policy_inputs_missing` with `missing_inputs` when required citations are missing
- Wired comparability determination objects into molecule/program report payload surfaces.
- Added deterministic tests for policy loading, precedence, completeness, downgrade behavior, and repeatability.

Files changed:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/comparability_policy_v0_2.json`
- `psi/services/comparability.py`
- `psi/services/report_engine.py`
- `tests/test_comparability_resolution.py`
- `tests/test_v3_catalog_immutability.py`

Gates run:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -c "import psi; from psi.services import reports_v3; print('import-ok')"` — PASS

Rsync overlay instructions:
- `rsync -av --delete ~/psi_codex/_artifacts/v1.3.0/overlays/psi_overlay_v1.3.0a64_<timestamp>/ ~/psi_repo/`

## 2026-03-02 — v1.3.0a63
Summary:
- Fix comparability category resolution precedence to enforce:
  - `missing_data=True` => deterministic conservative fallback `resolved_status="not_comparable"` with `resolution_reason="missing_data"`.
  - `missing_data=False` => policy-order precedence where earliest status in `allowed_statuses` present in input statuses wins, with `resolution_reason="policy_precedence"`.
- Add dedicated comparability resolution tests for precedence and partial-data determinism.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `tests/test_comparability_resolution.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-03-02 — v1.3.0a62
Summary:
- Fix report detail template contract requirements by adding a deterministic structured payload block with fixed keys and required literal markers.
- Always render fixed-order keys: `identity_context`, `molecule_report`, `policy_summary`, `rule_summary`, `measurement_summary`, `evidence_summary`, using deterministic `"missing"` placeholders when absent.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/reports/detail.html`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS

## 2026-02-26 — v1.2.9x32 (Closeout hardening)
What changed:
- Archived legacy MVP app source to `docs/legacy/legacy_mvp_app.py` and replaced `psi/legacy_mvp_app.py` with an overlay-safe tombstone shim so it is not part of active PSI runtime paths.
- Added GitHub Actions CI workflow (`.github/workflows/ci.yml`) running `compileall`, `pytest -q`, and `di_contract_smoke` with an ephemeral SQLite DB prepared by new tooling (`psi.tools.prepare_ci_db`).
- Added targeted `DeprecationWarning` emission when the legacy YAML engine entrypoints (`load_rules`, `run_decision`) are actually used; normal JSON DI paths remain silent.
- Typed SoE core builder config via `SoECoreConfig` dataclass (behavior-preserving compatibility shim retained internally).
- Extracted DI compute integrity hash finalization into `_finalize_integrity(...)` (behavior-preserving refactor) and added deterministic coverage.
- Added `progress_policy_v0_2.json` + explicit `load_progress_policy_latest()` mapping; molecule header now uses the deterministic latest progress policy loader.
- Added `template_prerequisites_v0_2.json` to cover current template versions used by progress policy latest.
- Added `confidence_policy_v0_3.json` (policy-visible multi-template aggregation strategy metadata, no weights) + explicit `load_confidence_policy_latest()` mapping.
- Added policy-visible replay compat catalog (`replay_policy_compat_v0_1.json`) and default-off verifier compat fallback wiring with audited `policy_resolution` metadata (strict exact-hash replay remains default).
- Added deterministic molecule-header regression lock fixture/test and strengthened smoke coverage for progress/confidence latest loaders, replay compat catalog, YAML deprecation warning, and integrity helper determinism.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/legacy_mvp_app.py`
- `docs/legacy/README.md`
- `docs/legacy/legacy_mvp_app.py`
- `.github/workflows/ci.yml`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- `psi/core/decision_engine.py`
- `psi/services/di/soe.py`
- `psi/services/di/compute.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/progress_policy_v0_2.json`
- `psi/core/di/catalogs/template_prerequisites_v0_2.json`
- `psi/core/di/catalogs/confidence_policy_v0_3.json`
- `psi/core/di/catalogs/replay_policy_compat_v0_1.json`
- `psi/services/molecule_header.py`
- `psi/services/di/verify.py`
- `psi/tools/prepare_ci_db.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_di_contract_smoke_pytest_wrapper.py`
- `tests/test_molecule_header_model.py`
- `tests/test_compute_finalize_integrity.py`
- `tests/fixtures/molecule_header_model_lock_v1.json`

Determinism/Replay note:
- DI semantics and snapshot semantics are unchanged; replay compat fallback is explicit and default-off.
- Replay strictness remains enforced (`matched=5, failed=0, skipped=0` required).

## v1.2.9w46

Why:
- Make the DI snapshot UI more audit-friendly with deterministic ordering and clearer error snapshot rendering.

What changed:
- `get_snapshot_detail` now provides `di_snapshot_ui` with pre-ordered gate outcomes, outcomes history, ranking candidates, and a unified DI error block.
- DI snapshot template uses pre-ordered lists for gate summary counts and outcomes history, renders a deterministic ranking candidates table, and surfaces a clear DI error snapshot block.

What did NOT change:
- No DI scoring/selection logic changes. No schema changes. No layout overhaul.

## 2026-02-26 — v1.2.9x28
What changed:
- Molecules overview (`/molecules`) now shows per-molecule progress and confidence bars using the existing deterministic molecule header model (read-only DI history + measurements; no DI logic changes).
- Molecule detail annotations panel adds bulk highlight controls for `oxidation_susceptible` and `deamidation`, plus clear highlights and click-to-deselect for highlighted residues.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/routers/molecules.py`
- `psi/web/templates/molecules/list.html`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- Presentation-layer only patch; DI engine, policies, registry semantics, and snapshot hash-bearing outputs are unchanged.
- Molecule list header bars reuse existing deterministic header model builders with explicit ordering preserved.

## 2026-02-26 — v1.2.9x29
What changed:
- Molecule detail annotations list now removes per-site `oxidation_susceptible` and `deamidation` rows entirely.
- Added per-component summary rows directly under the Full sequence viewer section with `Highlight` + `Deselect` buttons for oxidation/deamidation (no Copy buttons on these rows).
- Existing Copy buttons for all other annotation items remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- UI-only template/JS behavior change; no DI, policy, registry, or schema changes.
- Replay surfaces and snapshot hashes remain unchanged.

## 2026-02-26 — v1.2.9x30
What changed:
- Motifs/Liabilities section now renders summary rows with `Highlight` + `Deselect` (no Copy) for `N_glycosylation`, `Oxidation susceptible`, and `Deamidation susceptible`.
- Removed the x29 oxidation/deamidation summary-row placement under the Full sequence viewer block.
- Per-site annotation rows remain removed for oxidation/deamidation, and `N_glycosylation` now uses the summary-row pattern instead of per-item Highlight+Copy.
- Copy buttons elsewhere remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- UI-only template/JS change; no DI outputs, policy semantics, registry semantics, or schema behavior changed.
- Highlight union logic uses deterministic component annotation data already present in the page model.

## 2026-02-26 — v1.2.9x31
What changed:
- Motifs/Liabilities row-level `Deselect` now clears highlights only for that specific motif/liability row (`N_glycosylation`, `oxidation_susceptible`, or `deamidation`) instead of clearing the entire component.
- Multi-row motif/liability highlights can now coexist, and the viewer renders the union deterministically.
- Click-to-deselect on highlighted residues now removes the residue from active highlight sets covering that residue without clearing unrelated motif highlights.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`

Determinism/Replay note:
- UI-only template/JS refinement; no DI/policy/registry/schema changes.
- Highlight state remains deterministic and component/feature-scoped in the browser only (no snapshot impact).

## v1.2.9w45

Why:
- Add stable evidence pointers so audit users can trace gate/readiness/shortlisting/ranking “why” back to concrete inputs.

What changed:
- Added additive `output.why_evidence` with deterministic sub-blocks for `gates`, `readiness`, `shortlisting`, and `ranking`.
- Evidence pointers are direct references only (measurement IDs, data_record IDs, and selected evidence field pointers already present in selected inputs).
- `di_contract_smoke` now asserts `why_evidence` presence, ordering, and gate-pointer coverage when gate metrics are present.

What did NOT change:
- No new ranking factors. No heuristic inference. No schema changes.

## v1.2.9w44

Why:
- Render outcome labels and DI review verdicts in the snapshot UI as read-only audit context.

What changed:
- `get_snapshot_detail` now exposes `latest_outcome_label` with latest-wins semantics (excluding DI review label rows).
- DI snapshot UI shows latest outcome label + latest DI review verdict/rationale read-only and removes inline label write forms from the snapshot panel.
- `di_contract_smoke` renders the DI snapshot template with/without labels to verify no render errors.

What did NOT change:
- No DI output schema changes. No labeling semantics changes. No new tables.

## v1.2.9w43

Why:
- Surface DI snapshot provenance explicitly in the snapshot UI and lock the contract with smoke assertions.

What changed:
- DI outputs now include additive provenance sub-blocks for template, policy ref, and decision scope.
- Decision snapshot detail context exposes explicit `di_snapshot_provenance` for Jinja rendering.
- DI snapshot template renders policy/template/version/hash, shortlisting-enabled, and scope identifiers.
- `di_contract_smoke` asserts provenance fields exist for batch + molecule snapshots and remain deterministic across reruns.

What did NOT change:
- No schema changes. No DI scoring/heuristics changes. No labeling semantics changes.

## v1.2.9v15 (final-2)

Why:
- Replay regression failed on WAL databases when opened with driver-level read-only.

What changed:
- `ensure=False` now opens a normal SQLite connection, installs `PRAGMA query_only=1`, and skips WAL/synchronous pragmas to preserve read-only behavior without WAL I/O failures.

What did NOT change:
- Web app still uses WAL for writable DBs; no schema or DI changes.

## v1.2.9v15 (final-3)

Why:
- Read-only replay tools could crash on WAL databases with "attempt to write a readonly database" during SELECT.

What changed:
- `get_db(..., ensure=False)` now probes with `SELECT 1` and, on readonly-like errors, falls back to a temporary copy of the DB (and any -wal/-shm) in a writable temp directory. Read-only sessions set `PRAGMA query_only=1` and skip WAL/synchronous/busy_timeout.

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes. Web sessions still attempt WAL when writable.

## v1.2.9v16

Why:
- Replay read-only open now uses a schema-touching probe; WAL-safe shadow copy fallback with stability loop; no writes to target DB.

What changed:
- `psi/core/db.py`: read-only `get_db(..., ensure=False)` probes `decision_snapshots`, falls back to a temp copy (db + wal/shm) if WAL coordination fails, and enforces `PRAGMA query_only=1` in read-only sessions. Session is configured as read-only (no autoflush, no expire_on_commit).

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes.

## v1.2.9v15 (final)

Why:
- Replay tools crashed because WAL requires sidecar files and can fail under read-only/locked DB access.

What changed:
- `ensure=False` now uses driver-level SQLite read-only URI mode and skips WAL/synchronous/busy_timeout pragmas.

What did NOT change:
- Web app still uses WAL for writable DBs; no schema or DI changes.

## v1.2.9v15 (redo)

Why:
- Read-only tooling could fail when SQLite connect pragmas attempted WAL/synchronous on RO connections.

What changed:
- `psi/core/db.py`: compute writability from DB path and skip WAL/synchronous/busy_timeout pragmas when the path is not writable.

What did NOT change:
- No schema changes. No DI/policy changes. No snapshot content/integrity changes.

## v1.2.9v15

Why:
- Read-only tooling could fail when SQLite connect pragmas attempted WAL/synchronous on RO connections.

What changed:
- `psi/core/db.py`: skip WAL/synchronous when `PRAGMA query_only` indicates RO, and gracefully handle known read-only errors. Writable connections still enable WAL.

What did NOT change:
- No schema changes. No DI/policy changes. No snapshot content/integrity changes.

## v1.2.9v14

Why:
- Surface OutcomeLabel metadata directly on DI snapshot detail views.

What changed:
- Display OutcomeLabel rows in the DI snapshot detail panel (read-only).

What did NOT change:
- No schema changes. No DI logic changes. No DB writes.

## v1.2.9v13

Why:
- Clarify legacy YAML engine deprecation intent and surface a visual engine badge.

What changed:
- Docs: add a non-binding deprecation target note in `docs/DI_CONSTITUTION.md`.
- UI: display DI vs legacy YAML engine badge on decision list/detail views.

What did NOT change:
- No schema changes. No DI logic changes. No policy changes.

## v1.2.9v12

Why:
- Reduce rare race conditions in molecule/chain ID allocation.

What changed:
- Retry on IntegrityError when allocating molecule primary IDs and chain IDs.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v11

Why:
- Remove dead helper functions in molecules router to reduce confusion.

What changed:
- Deleted unused private helpers in `psi/web/routers/molecules.py` after verification.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v10

Why:
- Ensure `model_to_dict` includes all SQLAlchemy columns reliably.

What changed:
- Use SQLAlchemy column introspection for model serialization, with safe fallback to prior behavior.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v9

Why:
- Remove hardcoded DI catalog path and centralize it as a named constant.

What changed:
- Add `DEFAULT_CATALOG_PATH` next to `load_catalog` and use it in DI runner.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v8

Why:
- Ensure molecule background tasks can target an explicit DB path when provided.

What changed:
- Thread `db_path` into molecule background tasks and pass the active DB path from router scheduling.

What did NOT change:
- No schema changes. No DI logic changes. No UI changes.

## v1.2.9v7

Why:
- Remove remaining `datetime.utcnow()` usage and keep naive UTC timestamps in line with PSI conventions.

What changed:
- Replace all `datetime.utcnow()` call sites with `datetime.now(timezone.utc).replace(tzinfo=None)`.

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes.

## v1.2.9v6

Why:
- Reduce SQLite lock contention for concurrent local sessions.

What changed:
- Set SQLite PRAGMAs on connect: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`.

What did NOT change:
- No schema changes. No DI/policy changes. No UI changes.
- WAL creates runtime sidecar files (`*.sqlite-wal`, `*.sqlite-shm`); never include these in overlay ZIPs.

## v1.2.9v5

Why:
- Remove FastAPI startup deprecation while preserving deterministic startup semantics.

What changed:
- Migrate startup hook to a FastAPI lifespan context manager.

What did NOT change:
- No schema changes. No DI/policy changes. No endpoint/UI changes.

## v1.2.9v4

Why:
- Eliminate Python 3.12 datetime.utcnow deprecation and enforce consistent UTC helper usage.

What changed:
- Add/standardize `now_utc()` in `psi/core/utils.py` (naive UTC) and replace all `datetime.utcnow()` call sites.

What did NOT change:
- No schema changes. No DI/policy changes. No functional decision changes.

## v1.2.9v3

Why:
- UI readability polish for drift explanations and SQL IN-clause hardening.

What changed:
- UI: improved DI drift explain panel readability; reason legend; no functional change.
- Hardening: replace f-string IN-clause SQL with SQLAlchemy expanding bindparams across codebase.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9v2

Why:
- Surface DI verification + drift intelligence in the UI (anchored vs current-world), read-only.

What changed:
- `psi/web/routers/decisions.py` + `psi/web/templates/decisions/_di_snapshot.html` + `psi/web/templates/decisions/_di_verification.html`: add DI verification panel with anchored/current status + drift explain.
- `psi/services/programs.py` + `psi/web/routers/programs.py` + `psi/web/templates/programs/detail.html`: optional lineage verification chips via `?verify=1`.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9v1

Why:
- di_cross_version_stress should treat DATA_DRIFT as expected and non-failing.

What changed:
- `psi/tools/di_cross_version_stress.py`: DATA_DRIFT now WARN (non-failing); hard fail only on anchored mismatch, exceptions, or non-data-drift classifications; add classification histogram; exit nonzero only on hard failures.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9v

Why:
- Governance hardening for packaging, dashboard visibility, and verification tooling.

What changed:
- `compress.sh` + `PSI_CONTEXT.md`: desktop shortcut install is opt-in and must be run from `~/psi_repo`.
- `psi/services/programs.py` + `psi/web/templates/programs/detail.html`: add DI snapshot lineage panel (read-only).
- `psi/tools/di_cross_version_stress.py`: read-only cross-version verification stress test tool.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9u

Why:
- Finish deterministic, read-only portfolio analytics surfaces and clarify decision lifecycle in molecule history.

What changed:
- `psi/services/programs.py` + `psi/web/templates/programs/detail.html`: add gate failure frequency, metric coverage frequency, and QC instability summaries (counts only).
- `psi/services/molecules.py` + `psi/web/templates/molecules/detail.html`: surface superseded status in decision history.

What did NOT change:
- No DI engine logic changes. No policy changes. No DB writes or schema changes.

## v1.2.9s3

Why:
- Make replay regression harness startup clearer and fail fast on invalid explicit DB paths.

What changed:
- `psi/tools/di_replay_regression.py`: print PSI version + read-only mode; fail fast if `--db` path is missing.

What did NOT change:
- No DI logic changes. No DB writes. No schema changes.

## v1.2.9s2

Why:
- Clarify which SQLite DB path the replay regression harness opens, and enforce read-only posture.

What changed:
- `psi/tools/di_replay_regression.py`: print resolved DB path at startup; open DB with `ensure=False`.

What did NOT change:
- No DB schema changes. No DB writes. No DI logic changes.

## v1.2.9s

Why:
- Fix a startup crash (`IntegrityError: UNIQUE constraint failed:
  ux_decision_snapshots_one_active_per_scope`) that fires on every PSI
  startup after the first time the q-series supersession index was created.

Root cause:
- `ensure_schema()` in `psi/core/db.py` ran a blanket
  `UPDATE decision_snapshots SET is_superseded=0 WHERE is_superseded IS NULL`
  on every startup. On the first run this was safe (the unique index did not
  exist yet). On every subsequent run the unique index already exists, and if
  any rows had `is_superseded IS NULL` (produced by `create_snapshot_freeze`
  or any pre-q-series snapshot), converting them all to 0 simultaneously
  violates the index when two or more such rows share the same scope tuple.
  The dedup step that would have cleaned up duplicates ran after the blanket
  conversion — too late.

- Secondary cause: `create_snapshot_freeze` never set `is_superseded` at all,
  leaving every freeze snapshot with `is_superseded IS NULL`. These silently
  accumulated and triggered the crash on the next startup.

What changed:
- `psi/core/db.py` (`ensure_schema`): replace the blanket NULL→0 backfill
  with a safe per-scope algorithm:
    1. Early-exit if no NULL rows exist (idempotent, zero cost on clean DBs).
    2. For each affected scope, fetch all candidate-active rows (NULL or 0)
       ordered newest-first.
    3. Mark all losers `is_superseded=1` FIRST — this only removes rows from
       the active set and can never violate the unique index.
    4. Set the remaining NULLs (now guaranteed: at most one per scope) to 0.
  This is safe on first run, safe on all subsequent runs, and idempotent.

- `psi/services/decisions.py` (`create_snapshot_freeze`): explicitly set
  `is_superseded=0` on every new freeze snapshot. Prevents future NULL
  accumulation from this path.

What did NOT change:
- No DI engine logic changes. No policy changes. No selector changes.
- No snapshot content changes. No integrity hash changes.
- `runner.py` supersession logic is untouched (already correct).

## v1.2.9r3

Why:
- Constitution hardening: clarify DI scope, patch governance, and the legacy YAML engine boundary.

What changed:
- `docs/DI_CONSTITUTION.md`
  - Add explicit scope + canonical DI surfaces list (what the Constitution governs).
  - Add patch governance requirements (required sanity commands + second-pass review triggers).
  - Clarify legacy YAML rules engine boundary vs canonical DI engine.
  - Refine Drift Guards wording: disallow scoring/ranking/adaptive tables while permitting deterministic audit/provenance/labeling tables (e.g. `OutcomeLabel`).

What did NOT change:
- Docs-only patch: no DI engine changes, no policy changes, no selector changes.
- No DB changes / migrations.
- No snapshot contract changes.

## v1.2.9r2

Why:
- Restore DI Snapshot Contract invariant: anchored replay must reproduce the stored `snapshot_content_hash` exactly.
- v1.2.9r1 correctly prevented legacy anchored replay from "seeing the future" by using an effective `as_of_ts=snapshot.created_at`, but this changed the replay output surface (`provenance.as_of_ts`) for snapshots that originally stored `as_of_ts=null`, causing a contract smoke regression.

What changed:
- `psi/services/di/verify.py`
  - Anchored replay still computes with an effective `as_of_ts` for legacy snapshots (prevents future influence).
  - Verification-only surface alignment now mirrors stored `provenance.as_of_ts` (including `null`) onto the anchored replay output and recomputes integrity hashes on the adjusted payload.

What did NOT change:
- No policy changes. No selector changes. No DB changes / migrations.

## v1.2.9r1

Why:
- Fix anchored replay determinism for legacy snapshots where `inputs_json.as_of_ts` is null.
- Without an explicit as-of timestamp, replay runs at "now" and can drift on summary surfaces (e.g. SoE evidence_summary timestamps/counts), even when the anchored evidence IDs are unchanged.

What changed:
- `psi/services/di/verify.py`
  - Split verification into two DI inputs:
    - current-world recompute keeps `as_of_ts=None` (interpreted as "now")
    - anchored replay uses `as_of_ts=snapshot.created_at` when the snapshot omitted `as_of_ts`
  - Add a small verification-only legacy alignment step for anchored replay when the stored snapshot has a type mismatch in `provenance.inputs_fingerprint.scope_id`:
    - copy the stored value into the replay output
    - recompute integrity hashes on the adjusted payload (read-only)

What did NOT change:
- No schema changes. No migrations.
- No DI engine / policy / selector logic changes.
- No mutation of existing snapshots.

## v1.2.9r

Why:
- Add an institutional replay regression harness to continuously validate that persisted DI snapshots can be deterministically replayed via the anchored replay path.
- This is a read-only hardening layer: it does not change DI governance rules, policy semantics, selector semantics, or snapshot persistence.

What changed:
- New CLI tool: `python -m psi.tools.di_replay_regression`
  - Enumerates stored `decision_snapshots` deterministically.
  - For each snapshot, runs the existing verification service anchored replay path and gates on `stored_vs_replay_classification == VERIFIED`.
  - Emits a clear, deterministic report with per-snapshot failures and a minimal semantic diff snippet (excluding volatile fields).
  - Exit code 0 if all pass; non-zero if any fail.

Determinism + governance notes:
- Replay is read-only and must not write new snapshots or mutate existing snapshots.
- Policy is resolved by the snapshot-stored `policy_id` + `policy_version` (no fallback to latest).
- Semantic diff ignores explicitly-volatile fields (as defined by the verifier):
  - `outputs.engine.code_version`
  - `outputs.provenance.integrity`

What did NOT change:
- No schema changes. No migrations.
- No DI engine logic changes. No policy changes. No selector changes.
- No changes to integrity hashing functions or verification classifications.

## v1.2.9q8a

Why:
- Hotfix: v1.2.9q8 patch for `psi/services/decisions.py` was missing `from sqlalchemy import text`, causing a runtime `NameError` when the legacy `run_and_snapshot()` path executes.
- This hotfix adds the missing import only. No logic changes beyond v1.2.9q8.

## v1.2.9q8

Why:
- Fix two logic bugs in `psi/services/decisions.py` introduced by the v1.2.9q
  supersession patch. Both are runtime failures; neither is a syntax error and
  neither is caught by compileall.

Bug 1 — `run_and_snapshot` never creates a snapshot on the first run:
  The snapshot creation block (`snap = DecisionSnapshot(...)` and all code
  after it) was accidentally nested inside `if active_ids:`. On the first run
  for any scope, `active_ids` is empty, the branch is skipped, and the function
  returns `None`. The web router then crashes with AttributeError accessing
  `snap.id` on None. Every first-time "Run DI" or legacy decision button press
  would 500.
  Fix: move `snap = DecisionSnapshot(...)` and everything following it to
  function scope. The mark-superseded UPDATE stays conditional (only runs when
  there are prior actives). Snapshot creation is now unconditional.

Bug 2 — `create_snapshot_freeze` raises NameError at runtime:
  The function referenced `active_ids` at lines 220–221, a variable that only
  exists in `run_and_snapshot`. `create_snapshot_freeze` never queries for
  prior snapshots and has no `active_ids` of its own. Any call to this function
  would raise `NameError: name 'active_ids' is not defined`.
  Fix: remove the stray `if active_ids:` block entirely from
  `create_snapshot_freeze`. The function now creates the snapshot and commits
  without attempting supersession (which it was never intended to do).

What did NOT change:
- No DI engine logic changes. No policy changes. No selector changes.
- No schema changes. No migrations.
- runner.py supersession logic is untouched (it was correct).
- db.py is untouched.
- models.py is untouched.

## v1.2.9q7
- Hotfix: fix runtime NameError in `psi/services/di/runner.py` (`scope_batch_id` undefined inside `compute_di_output()`).
- Structural-only change: define `scope_batch_id = int(di_input.scope_id)` within `compute_di_output()` so selection calls are self-contained; no governance logic changes.
## v1.2.9q5
- Hotfix: fix v1.2.9q overlay corruption in `psi/services/di/runner.py` that deindented the governed snapshot return path, causing `SyntaxError: 'return' outside function`.
- Structural-only change: restore correct block structure so snapshot creation + supersession update executes inside the intended function (no logic changes).
## v1.2.9q6
- Hotfix: restore structural correctness in `psi/services/di/runner.py` (supersession + snapshot creation code re-indented inside `run_di()`).
- No logic changes beyond repairing overlay corruption; governance additions preserved.
## v1.2.9q4
- Hotfix: fix remaining v1.2.9q overlay corruption in `psi/services/decisions.py` where the supersession block was deindented to module scope, causing `SyntaxError: 'return' outside function`.
- Structural-only change: re-indent the governed snapshot path so all logic executes inside `run_and_snapshot()`.

## v1.2.9q3
- Hotfix: restore syntactically valid `psi/services/decisions.py` after v1.2.9q overlay corruption caused `SyntaxError: 'return' outside function`.
- No logic changes intended; file content restored to the v1.2.9q governed snapshot path with correct block structure.

## v1.2.9q2 — Hotfix: Restore schema/model structural integrity (no logic changes)

Fixes patch-overlay structural corruption introduced in v1.2.9q:

- `psi/core/db.py`: ensure v1.2.9q supersession backfill + index creation stays inside `ensure_schema()` / proper `with eng.begin()` scope (prevents `IndentationError` / stray module-level execution).
- `psi/core/models.py`: restore truncated `DataRecord.raw_inputs_json` line and place snapshot supersession columns inside `DecisionSnapshot` where they belong (fixes syntax break + correct ORM placement).

No behavior changes beyond restoring intended code placement and importability.


## v1.2.9q

Why:
- Governance hardening: institutionalize snapshot lifecycle clarity without changing DI logic or replay determinism.

What changed:
- Add snapshot supersession metadata (`is_superseded`, `superseded_by_snapshot_id`, `superseded_at`) (additive).
- Enforce single ACTIVE snapshot per scope `(decision_key, program_id, molecule_id, batch_id)` transactionally on snapshot insert.
- Add deterministic backfill to mark older snapshots as superseded per scope on existing DBs.
- Add a partial unique expression index to guarantee at most one ACTIVE snapshot per scope under SQLite NULL semantics.
- UI: Decisions list + detail pages display ACTIVE/SUPERSEDED status and (when present) the superseding snapshot link.
- Smoke test: future-proof cross-version patching to include verify module PSI_VERSION if it is ever introduced.

Notes:
- Snapshot content immutability is preserved: governance fields are metadata and are excluded from DI semantic hashes.

## v1.2.9p

Why:
- Complete the remaining DI v0.6 UI transparency surfaces without changing DI engine behavior.

What changed:
- Molecule detail UI: add a contextual **Run DI** entry point linking to `/decisions/new` with `program_id` + `molecule_id` prefilled.
- Batch Decisions tab UI: add **Run DI for this batch** entry point (and show it even when there are no snapshots yet) with `program_id` + `molecule_id` + `batch_id` prefilled.
- Decisions "Run Decision" form UI: parse query params (`program_id`, `molecule_id`, `batch_id`) to preselect scope inputs deterministically (navigation-only; no DI logic changes).
- Snapshot detail UI (`decisions/_di_snapshot.html`):
  - Add **SoE Coverage** section rendering stored `soe_v0_3` (or `soe_v0_2` fallback) metric status + required/optional grouping + gate coverage, with deterministic ordering.
  - Add `decision_output_hash_v2_effective` display in the integrity section.

Governance hygiene:
- Verified `compress.sh` includes `docs/DI_MISSION_AND_ROADMAP.docx` and `PSI_CONTEXT.md` accurately reflects this (no changes required).

What did NOT change:
- No DI engine logic changes. No policy changes. No selector changes.
- No DB changes / migrations.


## v1.2.9o2
- Fix DI contract smoke cross-version test to use current create_data_record/upsert_measurements signatures.
- Ensure cross-version test references packaged advance_to_in_vivo_v0_1 policy path.

## v1.2.9o

Why:
- Normalize the snapshot integrity surface so `snapshot_content_hash` remains stable across code version upgrades.
- Prevent false drift / verification noise caused by `outputs.engine.code_version` changing between releases.

What changed:
- `psi/services/di/integrity.py`: exclude `outputs.engine.code_version` from `snapshot_content_hash` payload (while keeping it in stored outputs JSON).
- `docs/DI_SNAPSHOT_CONTRACT.md`: document `outputs.engine.code_version` as metadata excluded from `snapshot_content_hash`.
- `psi/tools/di_contract_smoke.py`: add regression test simulating a cross-version verify by patching module PSI_VERSION between snapshot creation and verification.

What did NOT change:
- No readiness logic changes. No gate changes.
- No policy JSON changes. No selector changes.
- No DB changes / migrations.
- No UI changes.


## v1.2.9n5

Why:
- Fix `semantic_fingerprint` always returning `""` (empty string) in both stored
  and anchored replay verify output, causing the smoke test assertion
  `stored + replay semantic_fingerprint must be non-empty` to fail.

Root cause:
- `_semantic_fingerprint()` in `verify.py` called `compute_snapshot_content_hash()`
  with a single positional argument. That function requires three keyword arguments
  (`inputs_obj`, `outputs_obj`, `evidence_ids`). The call always raised `TypeError`,
  which was silently swallowed by the surrounding `except Exception: return ""`.
  The function has been broken since it was introduced; the n4 smoke test assertion
  exposed it by fixing the earlier `snapshot_content_hash` mismatch that was
  masking this failure.

What changed:
- `psi/services/di/verify.py`: `_semantic_fingerprint()` now computes
  `sha256(stable_json(stripped_outputs))` directly, which is what the function
  always intended — a self-contained hash of the output payload with volatile
  fields (`engine.code_version`, `provenance.integrity`) removed. `hashlib`
  moved to module-level import.

What did NOT change:
- No policy changes.
- No selector changes.
- No DB changes / migrations.
- No changes to `snapshot_content_hash`, `evidence_fingerprint`, or
  `decision_output_hash_v2` — those are correct and stable.

## v1.2.9n4

Why:
- Fix `snapshot_content_hash` mismatch between runner and anchored replay.
  Root cause: `scope_id` type inconsistency — runner stored `scope_id` as a string
  (from callers passing `str(b.id)`), but verify.py reconstructed `DIInput` with
  `scope_id=int(...)`. `compute.py` wrote `di_in.scope_id` directly into
  `outputs.provenance.inputs_fingerprint`, producing `"7"` (str) in stored outputs
  and `7` (int) in anchored replay outputs. `_stable_json` serializes these
  differently, causing `snapshot_content_hash` to differ.

What changed:
- `psi/services/di/compute.py`: normalize `scope_id` to `int` in
  `provenance.inputs_fingerprint`.
- `psi/services/di/runner.py`: normalize `scope_id` to `int` in `inputs_obj`
  at all 3 call sites.
- `psi/core/di/schema.py`: added `__post_init__` to `DIInput` to coerce `scope_id`
  to `int` at construction. Catches `str(b.id)` callers at the entry point.
- `psi/tools/di_contract_smoke.py`: fixed `scope_id=str(b.id)` → `int(b.id)`.

What did NOT change:
- No policy changes. No selector changes. No DB changes / migrations.

## v1.2.9n3

Why:
- Fix anchored replay snapshot_content_hash mismatch by ensuring runner and anchored replay compute operate on identical in-memory SoE types.

What changed:
- DI shared compute now normalizes `ignored_evidence` entries to `IgnoredEvidence` objects before SoE packing and downstream logic.

What did NOT change:
- No policy changes.
- No selector changes.
- No DB changes / migrations.

## v1.2.9o4
- Hotfix: di_contract_smoke cross-version test now passes policy_path as Path (fixes str.read_text crash) and restores valid module syntax.

## v1.2.9o5
- Hotfix: di_contract_smoke cross-version test now treats classification==VERIFIED as pass when verify_snapshot omits legacy 'ok' flag.

## 2026-02-23 — v1.2.9v23
Why:
- Align smoke_test guardrail with append-only PATCH_NOTES discipline (latest entry at file end).

What changed:
- `psi/scripts/smoke_test.py`: latest PATCH_NOTES header is now read from the last dated entry.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v24
Why:
- Version sync: verify + compare DI snapshot UI already exists in this repo; no new behavior required.

What changed:
- Version bump only (no code changes needed).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v25
Why:
- Harden SQL IN-clause usage to use SQLAlchemy expanding bind parameters.

What changed:
- `psi/services/molecules.py`: replace dynamic `IN (...)` string binds with `bindparam(expanding=True)`.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v26
Why:
- Standardize naive UTC helpers in service layers without altering timestamps.

What changed:
- `psi/services/qc.py`: route QC timestamps through `now_utc()` helper.
- `psi/services/measurements.py`: use `now_utc()` for default timestamp parsing fallback.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v27
Why:
- Document WAL journal-mode expectations for writable databases.

What changed:
- Version bump only (WAL pragmas already enforced on writable connections).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

Notes:
- Writable SQLite connections attempt `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`.

## 2026-02-23 — v1.2.9v28
Why:
- Complete hardening sweep: remove f-string SQL assembly and ensure background tasks target the caller DB.

What changed:
- `psi/services/measurements.py`: remove f-string SQL assembly for raw measurement queries/updates.
- `psi/tools/export_measurements.py`: remove f-string SQL for PRAGMA table introspection.
- `psi/tools/qc_measurements.py`: remove f-string SQL for QC updates.
- `psi/core/db.py`: remove f-string SQL for PRAGMA/ALTER statements.
- `psi/web/routers/molecules.py`: pass explicit DB path to background tasks via caller session bind.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No UI changes.

## 2026-02-23 — v1.2.9v29
What changed:
- `psi/services/di/enrich.py`: add deterministic metric value-function evaluation + interpretation gap detection.
- `psi/services/di/compute.py`: include metric evaluations in DI outputs and emit interpretation-gap risk flags.
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`: add policy-visible `metric_value_functions` and include `interpretation_gap` in risk flag categories.
- `psi/tools/di_contract_smoke.py` and `psi/tools/run_di.py`: default to the v0.2 policy file.

What did NOT change:
- No DB changes / migrations. No snapshot mutation.
- No scoring weights. No ML. No selector or gate logic changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v30
What changed:
- `psi/services/di/eval.py`: add deterministic shortlisting derivation with explicit refusal state.
- `psi/services/di/compute.py`: include shortlisting output when policy allows it.
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`: add policy-visible shortlisting guardrails.
- `psi/tools/di_contract_smoke.py` and `psi/tools/run_di.py`: default to v0.3 policy.

What did NOT change:
- No DB changes / migrations. No snapshot mutations.
- No scoring weights. No ML. No gate/selector behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v31
What changed:
- `psi/web/templates/decisions/_di_snapshot.html`: reorganize DI snapshot view for fast interpretation (top summary first).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No new routes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v32
What changed:
- `psi/services/decisions.py`: add OutcomeLabel taxonomy constants and include labels in snapshot export payload.
- `psi/web/routers/decisions.py`: add minimal POST handler to attach OutcomeLabel to a snapshot.
- `psi/web/templates/decisions/_di_snapshot.html`: add Outcome review section with a minimal label form.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

Notes:
- Outcome labels appear on the snapshot detail UI and in JSON export (`/decisions/{id}/export`).

## 2026-02-23 — v1.2.9v33
What changed:
- `psi/web/routers/molecules.py`: remove duplicate formatting helpers already present in the service layer.

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No route behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v34
What changed:
- `psi/core/utils.py`: model_to_dict now serializes all SQLAlchemy column attrs deterministically (superset of prior fields).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v35
What changed:
- `psi/web/templates/decisions/detail.html`: add engine badge (DI vs Legacy YAML) and deprecation warning for legacy engine.
- `docs/DI_CONSTITUTION.md`: document deprecation clock (v1.3.0 DI-default; legacy YAML read-only).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No engine selection changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v36
What changed:
- Version-only: ID allocation retry logic already present in `get_or_create_chain` and `create_molecule` (IntegrityError retry loop).

What did NOT change:
- No DI logic changes. No policy changes. No selector changes.
- No DB changes / migrations. No route behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v37
What changed:
- `psi/services/di/nbe.py`: catalog-driven NBE helper for deterministic experiment suggestions.
- `psi/services/di/compute.py`: emit catalog-driven `experiment_suggestions` and `recommended_experiments`.
- `docs/DI_SNAPSHOT_CONTRACT.md`: document experiment suggestion outputs and determinism rules.

What did NOT change:
- No DI gate/selector logic changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v38
What changed:
- DI post-hoc review capture via OutcomeLabel (verdict + rationale) on DI snapshot page.
- UI: add DI review form and show latest review alongside existing outcome labels.
- Service/router: accept DI review submissions without schema changes.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9v39
What changed:
- DI snapshot UI: clarified supersession status/labeling.
- DI snapshot UI: added “What to trust” verification box explaining hashes and drift labels.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No new routes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w01
What changed:
- Version-only: “Verify now” action already present on decision detail (POST `/decisions/{id}/verify`).

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No route behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w02
What changed:
- Verification UI: clearer status chips, evidence added/removed summary, and per-metric “Why?” block.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No verification logic changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w03
What changed:
- Version-only: no f-string SQL `IN (...)` constructions found; existing `IN :ids` uses already use expanding bindparams.

What did NOT change:
- No query semantics changes. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w04
What changed:
- Version-only: `now_utc()` helper already exists and there are no `datetime.utcnow()` usages to replace.
- Note: timestamps remain naive UTC for SQLite compatibility (current PSI convention).

What did NOT change:
- No query semantics changes. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w05
What changed:
- Version-only: FastAPI lifespan already implemented in `psi/web/app.py` (no `@app.on_event("startup")` remains).

What did NOT change:
- No startup behavior changes. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w06
What changed:
- Version-only: SQLite WAL mode already enabled via connect PRAGMAs in `psi/core/db.py`.
- Runtime note: WAL improves concurrency and reduces lock errors; rollback is removing the PRAGMA listener to return to default journal mode.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No query behavior changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w07
What changed:
- DI runner now loads the experiment catalog via a canonical loader (no hardcoded file paths in `runner.py`).

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations. No policy packaging changes.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w08
What changed:
- Background tasks in `psi/services/molecules.py` now derive and pass the active `db_path` instead of using import-time `SessionLocal`.
- Note: no behavior change in normal single-DB deployment; fixes alternate db_path correctness in tools/tests.

What did NOT change:
- No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w09
What changed:
- Version-only: duplicated router helpers already removed; router delegates to service layer for molecule business logic.

What did NOT change:
- No behavior changes intended. No DI semantics changes. No ML. No scoring weights.
- No DB changes / migrations.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w10
What changed:
- Governance: documented Legacy YAML engine deprecation timeline and risk statement.
- UI: decision views label engine type as “DI engine” vs “Legacy YAML engine” with a caution note.

What did NOT change:
- No decision semantics changes. No DI logic changes. No ML. No scoring weights.
- No DB changes / migrations. No enforcement of engine selection.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w11
What changed:
- Enforced policy value functions in gate evaluation (thresholds/caps now affect gate pass/fail).
- Added threshold-violation risk flags/blockers when present metrics fail policy-defined value functions.
- DI snapshot UI now shows a compact value-function evaluation table.

Why it changed:
- Policy-defined thresholds must be enforced; presence alone should not be treated as pass.

Determinism/contract impact:
- Deterministic; outputs remain additive (`metric_evaluations` already present, now used by gate logic).
- Snapshot contract unchanged; no schema changes.

Behavior changes:
- Gate outcomes and decision_state may change when a metric is present but out-of-range per policy.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w12
What changed:
- Shortlisting output now includes structured tie-break explanations and refusal reasons.
- DI snapshot UI renders tie-break explanations and refusal details.

Why it changed:
- v0.5 requires transparent tie-break reasoning; explanations must be visible to the scientist.

Determinism/contract impact:
- Additive fields only (`tie_break_explanations`), deterministic ordering preserved.
- No change to gate logic or policy semantics.

Behavior changes:
- None (explanations only).

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w13
What changed:
- Gates are now evaluated via a policy-driven evaluator (JSON-gate definitions), with templates acting as thin adapters.

Why it changed:
- Decouple gate logic from Python to honor policy-as-data and unblock multi-template evaluation.

Determinism/contract impact:
- No semantic change intended; gate outcomes/readiness remain equivalent to v1.2.9w12.
- Snapshot contract unchanged; output fields additive only.

Behavior changes:
- None intended (equivalence refactor).

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w14
What changed:
- Refactored DI enrichment into focused modules: `soe`, `metric_eval`, `risk_flags`, `coverage`.
- `enrich.py` now acts as a thin orchestration layer importing the same functions.

Why it changed:
- Improve maintainability by splitting the enrichment "god module" without changing behavior.

Determinism/contract impact:
- No semantic change intended; deterministic ordering preserved.
- Snapshot contract unchanged; no DB/schema changes.

Behavior changes:
- None intended (refactor-only).

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w15
What changed:
- Added a DI template registry keyed by decision_key and template_key.
- DI runner now resolves templates via the registry (no hard-coded decision_key stop).
- Unknown templates yield deterministic `unsupported_template` outputs (not_ready) instead of raising.

Why it changed:
- Enable multi-template support while keeping policy-as-data and deterministic behavior.

Determinism/contract impact:
- Deterministic output; no schema changes.
- Unsupported templates produce stable, explicit not_ready outputs.

Behavior changes:
- Unknown decision_key/template_key no longer raises; snapshot output is not_ready with governance warning.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w16
What changed:
- Added a second DI template: `ready_for_scaleup_screen` (policy + template adapter).
- Registered the new template in the DI template registry.

Why it changed:
- Prove multi-template DI support without altering existing `advance_to_in_vivo` semantics.

Determinism/contract impact:
- Deterministic output; no schema changes.
- Unsupported templates still produce stable `unsupported_template` outputs.

Behavior changes:
- New decision_key `ready_for_scaleup_screen` is now supported.
- No behavior change for `advance_to_in_vivo`.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w17
What changed:
- Expanded the experiment catalog with metric-specific experiment mappings.
- NBE suggestion mapping now uses metric_keys to map missing metrics to experiments deterministically.

Why it changed:
- Ensure every policy-referenced metric can yield actionable experiment suggestions when missing.

Determinism/contract impact:
- Deterministic ordering preserved; no schema changes.
- No changes to gate, ranking, or value-function semantics.

Behavior changes:
- Missing metrics now produce richer, metric-specific experiment suggestions.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w18
What changed:
- Added a dedicated "Run DI" UI entrypoint and form (batch-scoped).
- Wired DI run to the DI runner service; created DI snapshots from the UI.
- Clarified legacy YAML labeling and links (Run Legacy YAML).

Why it changed:
- Provide an explicit DI run flow while preserving the legacy YAML path.

Determinism/contract impact:
- No DI semantic changes; no schema changes.
- Anchored replay and DI contracts unchanged.

Behavior changes:
- Users can run DI from the UI for supported templates.

Gates run (limit 5; replay run twice):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w19
What changed:
- Fixed Jinja inline conditional syntax in DI verification template.

Why it changed:
- Prevent template rendering errors in the verification UI.

Determinism/contract impact:
- No semantic changes; display-only fix.

Behavior changes:
- None; template renders correctly instead of erroring.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w20
What changed:
- Added a Jinja template compilation guardrail to `psi.scripts.smoke_test`.
- Fixed a Jinja syntax error in `molecules/form.html` caught by the guardrail.

Why it changed:
- Prevent template syntax errors from shipping by failing smoke_test if any template fails to compile.

Determinism/contract impact:
- Deterministic; no runtime behavior changes; no schema changes.

Behavior changes:
- None in production; smoke_test now validates template compilation.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w21
What changed:
- Added Legacy YAML deprecation clock statement to `PSI_CONTEXT.md` (intent-only).

Why it changed:
- Align context doc with Constitution wording and clarify the DI default timeline.

Determinism/contract impact:
- Docs-only; no runtime or schema changes.

Behavior changes:
- None.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w22
What changed:
- Formalized DI snapshot supersession semantics in docs and queries.
- Latest snapshot rollups now use `superseded_by_snapshot_id IS NULL`.
- Added scope+superseded index for deterministic lineage queries.

Why it changed:
- Make snapshot lineage first-class and queryable without changing DI semantics.

Determinism/contract impact:
- No DI evaluation changes; deterministic ordering preserved.
- Snapshot contract now documents lineage metadata.

Behavior changes:
- "Latest" snapshot rollups exclude superseded snapshots.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w23
What changed:
- Added deterministic `drift_type` enum to DI snapshot outputs.
- Drift derivation uses evidence fingerprint, policy semantics hash, and comparability status.
- Snapshot contract updated to document drift_type derivation.
- DI contract smoke now resets its ephemeral DB to keep determinism checks stable.

Why it changed:
- Make drift classification first-class and reproducible across anchored replay.

Determinism/contract impact:
- Deterministic; no schema changes.
- Anchored replay reproduces `drift_type` via stored drift context.

Behavior changes:
- New `drift_type` field present in DI outputs.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w24
What changed:
- DI contract smoke now compares two identical fresh DB copies to avoid run-to-run cross-contamination.
- Added deterministic `state_transition` metadata to DI outputs, derived from prior active snapshot + drift_type.
- Snapshot contract updated to document `state_transition`.

Why it changed:
- Fix harness nondeterminism and make state transitions first-class without altering DI evaluation logic.

Determinism/contract impact:
- Deterministic; no schema changes.
- Anchored replay preserves legacy snapshots without `state_transition`.

Behavior changes:
- New `state_transition` field present on DI outputs when a prior active snapshot exists.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w25
What changed:
- Added structured `comparability` contract fields (`is_comparable`, `reason`, hash-change flags).
- Drift derivation now honors `comparability.is_comparable`.
- Snapshot contract updated with comparability fields.

Why it changed:
- Make comparability a first-class, reproducible contract surface.

Determinism/contract impact:
- Deterministic; no schema changes.
- Anchored replay preserves legacy snapshots without comparability.

Behavior changes:
- New `comparability` fields present in DI outputs.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w26
What changed:
- Added deterministic `diff_summary` to DI verification reports (when comparable + prior snapshot exists).
- diff_summary derives from a curated, contract-level diff surface (hashes excluded).
- Snapshot contract updated to document diff_summary.

Why it changed:
- Provide a governance/audit-friendly summary of structural changes.

Determinism/contract impact:
- Deterministic; no schema changes.
- Legacy snapshots remain byte-stable (diff_summary is report-only).

Behavior changes:
- Verification output may include `diff_summary` when comparable and prior snapshot exists.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w27
What changed:
- Decision detail now shows ACTIVE vs SUPERSEDED, superseded_by link, and superseded_at.
- Added scope-level snapshot history view with deterministic ordering.

Why it changed:
- Make lineage explicit and provide a history entry point for the same decision scope.

Determinism/contract impact:
- Deterministic UI/query only; no schema changes.

Behavior changes:
- New history page at `/decisions/{id}/history`.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w28
What changed:
- History page now supports selecting two snapshots and launching compare.
- Validation enforces exactly two selections with a deterministic order.

Why it changed:
- Enable scope-level compare workflow directly from the history list.

Determinism/contract impact:
- Deterministic UI wiring only; no schema changes.

Behavior changes:
- New “Compare selected” action on `/decisions/{id}/history`.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w29
What changed:
- History compare selection now posts stable `snapshot_ids` and redirects to compare.
- Compare page labels clarify ordering (A newer/higher id; B older/lower id).

Why it changed:
- Make history compare wiring explicit and deterministic.

Determinism/contract impact:
- Deterministic UI wiring only; no schema changes.

Behavior changes:
- Compare page now labels A/B ordering.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.scripts.smoke_test`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-23 — v1.2.9w30
What changed:
- Constitution and snapshot contract now explicitly allow controlled, policy-defined shortlisting (no scoring, no opaque ranking).
- Snapshot contract now documents shortlisting schema and deterministic ordering rules.
- NBE recommended_experiments is now de-duplicated by experiment_key with deterministic global ordering and triggered_by_blockers attribution.

Why it changed:
- Align governance docs to actual deterministic outputs and remove contradictions.

Determinism/contract impact:
- Deterministic; no schema changes.
- NBE recommended list ordering is stable across runs and replay.

Behavior changes:
- recommended_experiments is now de-duplicated and includes triggered_by_blockers.

Gates run (limit 5):
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-24 — v1.2.9w31
What changed:
- Determinism fix for di_contract_smoke via baseline cutoff env var: `PSI_DI_BASELINE_CUTOFF_ISO`.

Why it changed:
- Prevent drift baseline from walking forward between the two smoke runs.

Determinism/contract impact:
- If `PSI_DI_BASELINE_CUTOFF_ISO` is set and parses as ISO8601, drift baseline selection only considers snapshots with `created_at <= cutoff`.
- If the env var is absent or invalid, behavior is unchanged (invalid values emit a warning and are ignored).

Behavior changes:
- di_contract_smoke sets `PSI_DI_BASELINE_CUTOFF_ISO` once at process start (if not already set) and reuses it for both runs.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w32
What changed:
- Patch A hardening/determinism hygiene: normalize_ignored qc alias, stable_json canonicalization, ISO/QC util dedupe, context docs correction, remove program_id fallback.

Why it changed:
- Eliminate replay brittleness, hash authority drift, and silent lineage corruption.

Determinism/contract impact:
- Ignored evidence normalization accepts both qc_status and qc_source, canonicalizing to qc_source.
- Stable JSON hashing/printing uses a single canonical implementation.
- ISO parsing and qc flag status derivation are centralized and deterministic.
- Context knobs remain store-only inputs; no gating impact.
- Missing program_id now fails explicitly; no silent lineage fallback.

Behavior changes:
- run_di CLI and DI web route surface clear errors when program_id lineage is missing.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w33
What changed:
- Patch B: molecule scope aggregation (deterministic batch selection + aggregation rule; smoke + replay coverage).

Why it changed:
- Enable deterministic molecule-scope DI snapshots without changing batch semantics.

Determinism/contract impact:
- Molecule scope selects all batches for the molecule ordered by created_at asc, id asc; aggregation uses newest-first for per-metric selection.
- Selection provenance records ordered batch list and metric source batch ids; SoE/comparability aggregate over selected batches.

Behavior changes:
- DI runner accepts scope_type="molecule" and aggregates batch evidence deterministically.
- di_contract_smoke exercises molecule scope.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w34
What changed:
- Determinism hardening: preserve molecule batch order; canonicalize dict key ordering in outputs.

Why it changed:
- Keep molecule batch ordering stable end-to-end and avoid nondeterministic dict ordering in stable JSON surfaces.

Determinism/contract impact:
- Molecule batch_ids are de-duplicated without sorting (first-seen order preserved).
- Used-by-metric and metric source maps are serialized with stable key ordering.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w35
What changed:
- Patch C1: deterministic ranking + structured why (additive outputs; both scopes; smoke coverage).

Why it changed:
- Provide deterministic multi-candidate ranking output with transparent, structured factors.

Determinism/contract impact:
- Ranking object is additive and ordered deterministically; candidate ordering uses explicit score + tie-breakers.
- Molecule candidate set derives from ordered batch selection provenance; batch scope emits a single candidate.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w36
What changed:
- Ranking hardening: normalized factor semantics (direction drives sign), deterministic scoring.

Why it changed:
- Remove ambiguity in ranking factors while preserving deterministic ordering.

Determinism/contract impact:
- All ranking weights are positive magnitudes; direction controls sign during scoring.
- Missing or unparseable factor values score as 0.0.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w37
What changed:
- Patch C2: outcome labeling CLI (OutcomeLabel storage; add/list; DI review verdict+rationale).

Why it changed:
- Provide a deterministic CLI workflow for outcome labels without UI or schema changes.

Determinism/contract impact:
- Outcome labels are metadata only and do not affect DI outputs.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`

## 2026-02-24 — v1.2.9w38
What changed:
- Fix: add missing json import in decisions service (CLI regression fix)

## 2026-02-24 — v1.2.9w39
What changed:
- Governance fix: DI ranking/weighted scoring is now emitted only when policy shortlisting is explicitly enabled (`shortlisting.allow_shortlisting` / `allow`).
- Contract smoke now asserts ranking is present when enabled and absent when disabled.

## 2026-02-24 — v1.2.9w40
What changed:
- Required gate keys now policy/template-authoritative; removes hardcoded readiness keys; fixes multi-template correctness.
- Readiness and shortlisting fallback gate evaluation now derive required gates from policy ordering and gate metadata.

## 2026-02-25 — v1.2.9w41
What changed:
- Remove DI imports from legacy decisions service (`stable_json_dumps` now DI-owned via `psi.services.di.util`).
- Unify duplicated DI error output builder to reduce drift risk; snapshot error schema preserved.

## 2026-02-25 — v1.2.9w42
What changed:
- Snapshot supersession integrity hardening: write paths now reconcile to a single active snapshot per exact scope before commit (authoritative active semantics: `superseded_by_snapshot_id IS NULL`), with explicit rollback on write failure.
- DI contract smoke now asserts the one-active-snapshot-per-scope invariant after DI writes.
## 2026-02-25 — v1.2.9w47
What changed:
- Governance hardening: removed weighted ranking emission from canonical DI outputs (`output.ranking`) and removed the weighted ranking table from the DI snapshot UI.
- DI contract smoke now asserts weighted ranking is absent while deterministic output and snapshot rendering remain stable.

Why it changed:
- Canonical DI outputs/UI should not present or rely on a weighted-sum "one score" ranking; deterministic shortlisting/tie-break remains the policy-authorized path.

Determinism/contract impact:
- `shortlisting` remains deterministic and canonical; weighted ranking is no longer emitted in canonical snapshots.
- `why_evidence` structure remains additive-compatible, with `why_evidence.ranking.candidates` empty when no canonical ranking is emitted.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w48
What changed:
- `/di/run` now supports both `batch` and `molecule` scope types via a scope selector and separate scope inputs.
- GET query prefills work for both `batch_id` and `molecule_id`; POST now passes the selected scope type/id through to `DIInput`.

Why it changed:
- Complete v0.6 DI run usability for molecule-scope runs without changing DI compute behavior.

Determinism/contract impact:
- No DI compute/output changes; this is UI/router plumbing only.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w49
What changed:
- Confirmed and preserved DI run links on batch and molecule detail pages.
- Applied a small UI consistency polish on the molecule detail page DI action button label/style.

Why it changed:
- Improve DI run discoverability in the batch/molecule detail workflows with consistent call-to-action styling.

Determinism/contract impact:
- No DI compute/output or schema changes; template-only discoverability update.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w50
What changed:
- Implemented deterministic shortlisting reproducibility signal from SoE `evidence_summary` counts for required metrics (`total_count > 1` and `usable_count > 1`).
- Added reproducibility details to shortlisting tie-break payloads and tie-break explanations.
- DI contract smoke now asserts the reproducibility block is emitted when evidence summaries are present.

Why it changed:
- Complete the v0.5 tie-break chain reproducibility signal using existing deterministic SoE evidence summaries, without introducing weighted scoring.

Determinism/contract impact:
- Reproducibility signal ordering is deterministic (`metrics` ordered by metric key).
- No global score/ranking reintroduced; shortlisting remains deterministic and additive.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w51
What changed:
- Deduplicated DI `inputs_obj` construction in `runner.py` so success and deterministic error paths emit the same snapshot input keys.
- Added an additive/idempotent `ensure_schema()` backfill for `decision_snapshots.engine_key='di'` when `engine_key IS NULL` and `schema_version` indicates DI (`di.%`).
- Clarified DI integrity hash hierarchy docs and the `psi.services.di.enrich` shim/facade role (behavior unchanged).

Why it changed:
- Reduce maintenance drift and make DI metadata/integrity behavior easier to understand without changing canonical DI outputs.

Determinism/contract impact:
- No schema drops/renames; backfill only updates NULL `engine_key` rows and is safe to rerun.
- DI output behavior remains unchanged (helper extraction + docs only).

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w52
What changed:
- Byte-copied `advance_to_in_vivo_v0_3.json` from canonical `psi_repo` to restore exact bytes and prevent historical policy hash drift.
- Added opt-in context-aware policy package `advance_to_in_vivo_v0_4.json` with deterministic route-based functional gate branching (`SC` vs default) expressed in policy data.
- Threaded `DIInput.context` into derived gate-outcome evaluation and version-gated new context branch surfacing to v0.4+ only (`gate_outcomes.*.context_branch` and `output.context_evaluation`).
- DI run UI default policy selection remains pinned to `advance_to_in_vivo` v0.3; selecting v0.4 is explicit via policy dropdown.
- Replay verification now hard-pins policy resolution by stored policy hashes (exact match first) and skips locally drifted snapshots whose exact policy package is not available in repo (`policy_exact_match_not_found`).
- Anchored replay applies a legacy v0.3 surface scrub to prevent post-w52 context-branch fields from leaking into historical replay outputs.
- DI contract smoke asserts deterministic context-branch selection via pure gate derivation fixtures.

Why it changed:
- Make `route`/`model`/`study_intent` context knobs materially affect gate evaluation in a deterministic, policy-authoritative way without changing replay surfaces for historical snapshots.

Determinism/contract impact:
- Historical v0.3 snapshots retain their prior canonical output surface and policy hashes.
- New context branch surfaces are emitted only for v0.4+ outputs; branch selection is exact-match and deterministic.
- No scoring/heuristics introduced; schema compatibility preserved additively.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w53
What changed:
- Added v0.4-only deterministic shortlisting refusal extension fields: `refusal_reasons_text`, `tie_break`, and `candidates`.
- Added a deterministic reproducibility-count refusal trigger for v0.4 shortlisting (`total_count>1` and `usable_count>1` on required metrics).
- DI snapshot UI now shows stable refusal reason text when present.
- Replay scrub removes these v0.4 refusal extension fields from historical v0.3 replay outputs.

Why it changed:
- Make refusal-to-rank explicit and contract-stable for v0.4+ while preserving v0.3 replay surfaces unchanged.

Determinism/contract impact:
- v0.4 refusal extensions are deterministically ordered and text-normalized.
- Historical v0.3 replay outputs remain scrubbed to prior surfaces.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w54
What changed:
- Added v0.4-only explicit tie-break dimension payloads (`tie_break_dimensions` and `shortlisting.tie_break.dimensions`) with stable ordering and `implemented`/`deferred` statuses.
- Completed deterministic dimension coverage for readiness completeness, QC confidence, purity aggregation profile, reproducibility, and potency/functional (with explicit deferral reason when not policy-required).
- Replay scrub removes these v0.4 tie-break extension fields from historical v0.3 replay outputs.

Why it changed:
- Complete the tie-break hierarchy transparently without introducing any global score or weighted ranking.

Determinism/contract impact:
- Tie-break dimension keys and order are fixed and deterministic for v0.4+.
- v0.3 replay surfaces remain unchanged via replay scrub.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w55
What changed:
- Added v0.4-only additive `output.scope_semantics` with explicit batch-first ranking semantics and molecule derivation metadata (`best_ready_batch_per_molecule`).
- Scope semantics include deterministic batch-ranked and molecule-derived views, and respect shortlisting refusal (no fabricated rankings).
- DI snapshot UI now displays a read-only scope-semantics summary.
- Replay scrub removes `scope_semantics` from historical v0.3 replay outputs.

Why it changed:
- Codify batch-vs-molecule shortlisting semantics explicitly and auditably without introducing scores.

Determinism/contract impact:
- `scope_semantics` is emitted only for v0.4+ and is derived from deterministic inputs (`scope_type`, `scope_id`, `selection_provenance`, refusal state).
- v0.3 replay surfaces remain unchanged via replay scrub.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w56
What changed:
- Added shared pure sub-assessment helpers (`psi/services/di/sub_assessments.py`) and used them in both DI templates for baseline risk flags and decision-state derivation.
- Extended template registry metadata with deterministic dependency declarations and added a deterministic template dependency graph helper.
- Exposed template dependency graph additively in DI output/provenance for v0.4+ only.
- Replay scrub removes template dependency graph fields from historical v0.3 replay outputs.

Why it changed:
- Establish a minimal v1.0 baseline for multi-template DI governance and reusable deterministic sub-assessments.

Determinism/contract impact:
- Registry keys and dependency graph nodes/edges are emitted in deterministic order.
- Existing template behavior is preserved (metadata/additive surfaces only).
- v0.3 replay surfaces remain unchanged via scrub.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w57
What changed:
- Added minimal DI snapshot forms for structured post-hoc labeling (`outcome label type + note`, and `DI review verdict + rationale`) using the existing `/decisions/{snap_id}/outcomes` write path.
- Added deterministic server-side validation helpers for outcome labels and DI review submissions in `psi/services/decisions.py`.
- Router outcome POST handler now uses the shared validation helpers (behavior preserved; controlled keys and rationale requirements enforced server-side).
- DI contract smoke now tests validation helpers deterministically without DB writes.

Why it changed:
- Complete the v1.1 baseline structured outcome-labeling workflow without affecting DI decision logic.

Determinism/contract impact:
- Outcome label validation is deterministic and server-side authoritative.
- DI logic and snapshot computation outputs are unchanged.

Gates run (limit 5):
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
## 2026-02-25 — v1.2.9w58
What changed:
- Confirmed `/di/run` web execution supports both `batch` and `molecule` scope POSTs and DIInput passthrough.
- Tightened deterministic ordering for `/di/run` selector lists with explicit `created_at DESC, id DESC` ordering for batches and molecules.

Why it changed:
- Close the remaining audit gap for molecule-scope DI execution from the web form with stable selector ordering.

Determinism/contract impact:
- No DI engine logic changes.
- No replay surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-26 — v1.2.9x10
What changed:
- Added `psi/tools/ci_gate_suite.py` (optional, stdlib-only) to run the canonical 4 required gates in the same order used for operator patching.
- The tool streams command output and prints a stable summary JSON (`ci_gate_suite_v1`) with per-command return codes.
- Returns non-zero on the first failing gate.

Why:
- Provide a single deterministic command entry point for CI/humans without changing or replacing the existing gate tools.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/ci_gate_suite.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x11
What changed:
- Added `psi/core/di/policy_registry_manifest.json` (validation-only registry of policy filename, version, and package hash).
- Added contract smoke validation to verify the registry manifest entries are filename-sorted and match current package hashes deterministically.

Why:
- Introduce a committed policy package hash index for governance validation without changing runtime policy selection behavior.

Determinism/Replay note:
- Validation-only change; no DI runtime policy mutation or hash recomputation changes.
- Manifest is generated from deterministic file ordering and canonical package hashing via `load_policy`.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy_registry_manifest.json`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x12
What changed:
- Added strict exact versioned policy path resolver in `psi/core/di/policy.py` (`resolve_versioned_policy_path`).
- Updated replay policy resolution (`psi/services/di/verify.py::_resolve_policy_from_repo`) to use exact versioned filenames instead of directory-scan fallback for `policy_id + policy_version`.
- Added contract smoke assertion for strict resolver mapping (`advance_to_in_vivo + v0.5 -> advance_to_in_vivo_v0_5.json`).

Why:
- Tighten policy loading semantics to deterministic exact versioned filenames and remove implicit fallback behavior.

Determinism/Replay note:
- Resolution is stricter but deterministic and output-preserving with current versioned policy files present.
- Replay remains the proof target under strict skip-fatal enforcement.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy.py`
- `psi/services/di/verify.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x13
What changed:
- Hardened `psi.tools.di_replay_regression` with a pre-check that each replayed snapshot’s stored `policy_package_hash` exists in `psi/core/di/policy_registry_manifest.json`.
- Replay now fails explicitly on missing/unknown snapshot policy package hashes before anchored verification.
- Added contract smoke coverage ensuring the registry manifest contains the forward-default policy package hashes (`advance_to_in_vivo_v0_5`, `ready_for_scaleup_screen_v0_2`).

Why:
- Add a governance integrity assertion tying replayed snapshots to a committed registry of known policy package hashes.

Determinism/Replay note:
- Validation-only hardening over stored snapshot metadata; no DI runtime output changes.
- Replay remains strict (`failed=0`, `skipped=0`) for patch acceptance.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_replay_regression.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x14
What changed:
- Added governance diagnostic CLI `psi.tools.policy_hash_audit`:
  - current policy hashes (from repo files)
  - snapshot-referenced hashes (read-only DB)
  - deterministic mismatch report against `policy_registry_manifest.json`
- Added contract smoke determinism check for the audit report output shape/content on a fixed DB sample.

Why:
- Provide an operator-facing diagnostic to inspect policy hash state without mutating DB or policy files.

Determinism/Replay note:
- Read-only diagnostic tooling + validation only; no DI runtime semantics changes.
- Audit output ordering is explicit and stable.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/policy_hash_audit.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x15
What changed:
- Expanded deterministic ordering validation in `psi.tools.di_contract_smoke` for:
  - risk flag enrichment ordering with `medium`/legacy `moderate` equivalence
  - policy `blocker_suggestions` mapping key ordering
  - policy `gate_order` / `required_gate_keys` duplicate-free stability checks

Why:
- Harden deterministic governance checks without changing runtime DI behavior.

Determinism/Replay note:
- Validation-only patch; no DI compute/output/hash changes.
- Replay remains strict and skip-fatal from x10 onward.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x16
What changed:
- Added sidecar freeze metadata file `psi/core/di/policy_metadata_freeze.json` to carry immutable-policy warning text without modifying JSON policy bytes.
- Added contract smoke validation that the sidecar covers the expected legacy snapshot-referenced policy files and carries the freeze notice text.

Why:
- JSON policy files cannot safely include comments; a sidecar preserves the freeze banner intent without changing policy hashes.

Determinism/Replay note:
- No policy JSON content changes; legacy policy package hashes remain untouched.
- Validation-only metadata addition.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy_metadata_freeze.json`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x17
What changed:
- Added final governance consolidation smoke checks ensuring:
  - forward policy forks (`advance_to_in_vivo_v0_5.json`, `ready_for_scaleup_screen_v0_2.json`) use `medium`
  - legacy `moderate` vocabulary does not appear in the forward fork files
- Final version bump for the x08→x17 governance hardening chain.

Why:
- Close the chain with explicit deterministic validation of forward severity vocabulary without mutating legacy policy JSON.

Determinism/Replay note:
- Validation-only patch; no runtime DI behavior changes.
- Replay remains strict (`failed=0`, `skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x18
What changed:
- Governance repair: restored legacy snapshot-referenced policy JSON files to pre-mutation content (`moderate` severity vocabulary) using the pre-`x07` code snapshot baseline (`v1.2.9x06`) as the source of truth:
  - `advance_to_in_vivo_v0_1.json`
  - `advance_to_in_vivo_v0_2.json`
  - `advance_to_in_vivo_v0_3.json`
  - `advance_to_in_vivo_v0_4.json`
  - `ready_for_scaleup_screen_v0_1.json`
- Kept forward policy forks unchanged:
  - `advance_to_in_vivo_v0_5.json` remains `medium`
  - `ready_for_scaleup_screen_v0_2.json` remains `medium`
- Regenerated/realigned:
  - `psi/core/di/policy_immutability_manifest.json`
  - `psi/core/di/policy_registry_manifest.json`

Why:
- Repair legacy policy immutability breach so historical snapshot `policy_package_hash` resolution remains exact and replay-stable.

Determinism/Replay note:
- Legacy policy bytes were restored from a deterministic baseline snapshot artifact, not hand-edited.
- Forward-fork defaults remain active (`v0.5` / `v0.2`); runtime compat shims continue to handle legacy `moderate`.
- Replay strictness (`matched=5, failed=0, skipped=0`) is the acceptance proof.
- Archival orphaned policy packages (under `psi/core/di/policies/_orphaned_snapshot_packages/`) exist solely for historical snapshot hash resolvability and are non-active for new policy selection/defaults.
- Canonical legacy policy files remain restored to pre-mutation bytes; orphaned archival files preserve the accidental x17-mutated package bytes for exact replay lookup only.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`
- `psi/core/di/policy_immutability_manifest.json`
- `psi/core/di/policy_registry_manifest.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_1__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_2__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_3__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/advance_to_in_vivo_v0_4__x17_mutated_medium.json`
- `psi/core/di/policies/_orphaned_snapshot_packages/ready_for_scaleup_screen_v0_1__x17_mutated_medium.json`
- `psi/services/di/verify.py`
- `psi/tools/di_contract_smoke.py`
- `psi/tools/policy_hash_audit.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x19
What changed:
- Changed `psi.services.di.risk_flags.derive_risk_flags_enriched()` unknown/unmapped risk key fallback severity from `low` to `unspecified` (neutral semantics).
- Kept deterministic sorting with explicit rank ordering and `unspecified` placed after `low`.
- Added contract smoke assertion that unknown risk keys deterministically emit `severity=\"unspecified\"`.

Why:
- Unknown risk keys should be neutral/not-assessed rather than implicitly treated as low-severity concerns.

Determinism/Replay note:
- Deterministic categorical logic only; no weighted logic introduced.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x20
What changed:
- Extracted DI error-output builder body from `psi/services/di/runner.py` into new module `psi/services/di/error_output.py` (`build_di_error_output_payload`).
- Kept `runner._build_di_error_output(...)` signature intact as a thin delegating wrapper (no behavioral changes intended).
- Added an explicit contract-smoke alias test documenting the parity guard against happy-path top-level field drift.

Why:
- Reduce `runner.py` size/risk and isolate error-output shaping while preserving the existing parity guarantees.

Determinism/Replay note:
- Refactor + parity-validation hardening only; no intended DI output changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/error_output.py`
- `psi/services/di/runner.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x21
What changed:
- Moved weighted ranking-factor constants out of `psi/services/di/compute.py` into policy-as-data JSON:
  - `psi/core/di/catalogs/shortlisting_policy_v0_1.json`
- Added deterministic loader in `compute.py` for ranking weights with explicit defaults and stable key handling.
- Replaced in-Python numeric ranking constants (`50.0`, `5.0`, `3.0`, `2.0`, `1.0`, `0.5`) in `_build_ranking(...)` with policy-loaded values (same numeric values preserved).
- Added contract smoke schema/value checks for the shortlisting policy catalog.

Why:
- Reduce hidden weighted heuristics in Python and make the ranking weight surface explicit, versioned, and auditable.

Determinism/Replay note:
- Policy-as-data extraction only; weights remain identical to prior values.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/shortlisting_policy_v0_1.json`
- `psi/services/di/compute.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x22
What changed:
- Extracted weighted ranking / shortlisting helper cluster from `psi/services/di/compute.py` into new module `psi/services/di/shortlisting.py`.
- `compute._build_ranking(...)` now delegates to `shortlisting.build_ranking_payload(...)`.
- Policy-loaded ranking weights from x21 are now read in the dedicated module.

Why:
- Reduce `compute.py` size/risk and isolate the ranking/shortlisting-weight helper cluster without changing semantics.

Determinism/Replay note:
- Refactor + wiring only; no intended ranking or DI output changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/compute.py`
- `psi/services/di/shortlisting.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x23
What changed:
- Fixed `_build_progress_stage_advisory(...)` to aggregate ALL prerequisite stage blockers/advisories (deterministically) instead of returning only the first one.
- Added `blocked_by_items` list to the stage advisory payload while preserving `blocked_by_text` (now aggregated).
- Updated contract smoke to assert multi-blocker advisory aggregation and stable ordering.

Why:
- Scientist-first progress header should surface all deterministic stage blockers, not just the first advisory row.

Determinism/Replay note:
- UI/view-model only; no DI snapshot/hash changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecule_header.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x24
What changed:
- Added targeted deterministic pytest coverage for `psi.services.molecule_header._build_molecule_header_model` in `tests/test_molecule_header_model.py`.
- Coverage includes:
  - legacy `moderate` -> `medium` normalization in header risk counts/items
  - unknown severity -> `unspecified` neutral handling
  - stage advisory presence with `blocked_by_items` surfaced in header model

Why:
- Add direct pytest coverage for the core scientist-first molecule header view-model assembly without requiring DB/network dependencies.

Determinism/Replay note:
- Test-only additions; no runtime DI behavior changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_molecule_header_model.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x25
What changed:
- Added pytest wrapper test `tests/test_di_contract_smoke_pytest_wrapper.py` that runs `python -m psi.tools.di_contract_smoke` and fails on non-zero exit.

Why:
- Provide a pytest entrypoint for contract smoke so CI-style pytest runs can cover the deterministic contract checks without changing the existing CLI tool.

Determinism/Replay note:
- Test-only wrapper; no changes to contract smoke behavior or DI runtime logic.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_di_contract_smoke_pytest_wrapper.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x26
What changed:
- Documented the `moderate -> medium` compatibility shim and deprecation horizon in:
  - `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- Added inline comments in `psi/services/di/risk_flags.py` clarifying:
  - forward vocabulary is `medium`
  - `moderate` is legacy-only compatibility
  - deterministic rank equivalence is intentional
- Updated docs to reflect x19 behavior: unknown/unmapped risk flags now fall back to neutral `unspecified` (not `low`).

Why:
- Make the compatibility boundary explicit for operators and maintainers while preserving exact historical replay support.

Determinism/Replay note:
- Docs + comments only; no runtime logic changes in this patch.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x27
What changed:
- Added contract smoke validation that progress-policy early milestone metric keys are representable in the measurement registry field catalog (`psi.core.registry.DATA_SCHEMAS`) deterministically.
- Added `expr_yield_mgL` and `pk_t12_h` to `psi.core.registry.DATA_SCHEMAS` so progress-policy milestone metric keys are representable.
- Added a scoping note in `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md` documenting the legacy YAML engine dependency boundary and intended deprecation approach (no runtime changes).

Why:
- Tighten policy/data integrity checks for progress milestones and clarify the legacy-engine deprecation boundary without affecting DI behavior.

Determinism/Replay note:
- Validation + docs only; no runtime DI logic changes.
- Replay strictness remains the acceptance proof (`matched=5, failed=0, skipped=0`).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x08
What changed:
- Added immutable forward policy forks (new files only; no edits to legacy policy JSON):
  - `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
  - `psi/core/di/policies/ready_for_scaleup_screen_v0_2.json`
- Switched DI run-page default policy selection to the new versions (`v0.5` / `v0.2`) in `psi/services/di/web.py`.
- Added contract smoke lock asserting deterministic latest-policy selection resolves to the new forward forks.

Why:
- Move forward policy defaults without mutating historical policy packages that may already be snapshot-referenced.

Determinism/Replay note:
- Legacy policy files were not modified.
- New policy files are versioned additions only; replay for existing snapshots remains anchored to stored policy hashes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/web.py`
- `psi/tools/di_contract_smoke.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_5.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_2.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x09
What changed:
- Added committed baseline hash manifest `psi/core/di/policy_immutability_manifest.json` for policy files under `psi/core/di/policies/`.
- Added stdlib tool `psi/tools/policy_immutability_check.py` to validate policy file contents against the manifest (no rewriting).
- Added contract smoke invocation to fail gates if policy file content diverges from the committed immutability manifest.

Why:
- Prevent accidental mutation of snapshot-referenced policy JSON files while preserving deterministic replay integrity.

Determinism/Replay note:
- Validation-only hardening; no DI runtime semantics or policy loader behavior changes.
- Manifest hashes are deterministic SHA-256 of file bytes with stable file ordering.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/policy_immutability_manifest.json`
- `psi/tools/policy_immutability_check.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x10
What changed:
- Hardened `psi.tools.di_replay_regression` to exit non-zero when `skipped > 0` (in addition to `failed > 0`).
- Replay skips are now governance-fatal in CLI automation, not just informational.

Why:
- Enforce strict replay integrity for patch gating and prevent silent acceptance of unresolved anchored replay policy/hash mismatches.

Determinism/Replay note:
- Tooling/governance behavior only; no DI runtime compute/output changes.
- Current patch acceptance requires `matched=5`, `failed=0`, `skipped=0`.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_replay_regression.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x09
What changed:
- Updated `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md` to align operator notes with the currently shipped roadmap state through `w114` and the `x01-x08` tooling patches.
- Documented shipped structural hardening splits (header/sequence/viewer helpers), severity tiers in `policy_body` with fallback, and forward severity vocabulary (`high|medium|low`) with backward compatibility.
- Added a concise remaining-work status list without changing roadmap intent.

Why:
- Keep operator-facing implementation notes synchronized with actual shipped deterministic DI behavior and policy-as-data surfaces.

Determinism/Replay note:
- Docs-only patch; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x08
What changed:
- Added optional stdlib-only tool `psi/tools/code_size_report.py`.
- The tool prints a deterministic JSON report (stable target ordering) for key module sizes/LOC to help track growth in risk hot-spots.
- No enforcement behavior is introduced; it is informational only.

Why:
- Provide a simple deterministic guardrail for code-size drift without changing the required gate suite.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/code_size_report.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x07
What changed:
- Tightened forward policy severity vocabulary by replacing `moderate` with `medium` in risk severity tiers across shipped DI policy JSONs:
  - `advance_to_in_vivo_v0_1..v0_4`
  - `ready_for_scaleup_screen_v0_1`
- Preserved backward compatibility in `psi/services/di/risk_flags.py` by normalizing legacy `moderate` -> `medium` during policy severity loading.
- Updated severity sort ranking to treat `medium` and legacy `moderate` equivalently.

Why:
- Enforce a single forward severity vocabulary (`high|medium|low`) while keeping older snapshots/artifacts readable and deterministically classified.

Determinism/Replay note:
- Intentional policy-data semantics change for future policy semantics/package hashes where these policy files are used.
- Runtime compatibility preserves deterministic handling of historical `moderate` values if encountered.
- Replay regression `failed=0` remains the acceptance criterion.
- Replay skips observed and allowed: `policy_exact_match_not_found` on snapshots referencing pre-change policy package hashes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/tools/di_contract_smoke.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x06
What changed:
- Added optional stdlib-only regression harness `psi/tools/molecule_viewer_regression.py`.
- The harness builds minimal dict/namespace fixtures and validates stable viewer helper output shape and ordering expectations.
- Prints a stable success message (`OK molecule_viewer_regression`) and exits `0` on success.

Why:
- Add a lightweight deterministic regression check for the newly extracted viewer helper cluster without introducing test/runtime dependencies.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/molecule_viewer_regression.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x05
What changed:
- Added `psi/services/molecule_viewer.py` and moved the molecule viewer assembly helper cluster out of `psi/services/molecules.py`.
- Moved (without signature changes):
  - `_confidence_from_mismatches`
  - `domain_instances_by_component`
  - `build_feature_tracks`
  - `build_numbering_maps`
  - `build_viewer_v2_components`
- `molecules.py` now imports/re-exports the viewer helpers and uses them in molecule detail assembly.

Why:
- Continue reducing `molecules.py` size/risk by isolating a coherent viewer-assembly cluster without changing behavior.

Determinism/Replay note:
- Structural split only; no intended ordering or output changes.
- Replay regression is the proof target for unchanged DI/hash-bearing outputs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_viewer.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x04
What changed:
- Extracted the experimental/batch UI context helper cluster from `psi/services/molecules.py` into new module `psi/services/molecule_experimental.py`.
- Moved (without signature changes):
  - `get_molecule_experimental_context`
  - batch/QC/headline helper functions
  - `get_molecule_batch_ui_context`
- `molecules.py` now imports/re-exports these helpers as a thin coordinator.

Why:
- Continue reducing `molecules.py` size/risk by isolating a coherent UI-only helper cluster.

Determinism/Replay note:
- Structural split only; no intended behavior or ordering changes.
- Replay regression is the proof target for no DI output drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_experimental.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x03
What changed:
- Added optional stdlib-only helper `psi/tools/pytest_smoke.py`.
- Behavior:
  - runs `pytest -q` via `python -m pytest` when pytest is installed
  - prints stable `SKIP` message and exits `0` when pytest is unavailable

Why:
- Provide a convenient test runner entry point without changing the required gate suite or adding runtime dependencies.

Determinism/Replay note:
- Tooling-only change; no DI compute/output/hash changes.
- Replay regression remains the required proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/pytest_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x02
What changed:
- Added deterministic fixture lock for `decision_output_hash_v2`:
  - `tests/fixtures/decision_output_minimal_v1.json`
  - `tests/test_decision_output_hash_v2_lock.py`
- The test computes the hash via the existing integrity utility and asserts a pinned digest.

Why:
- Pin a representative semantic decision hash to catch accidental drift in canonical hashing behavior.

Determinism/Replay note:
- Dev/test-only additions; no runtime DI behavior changes.
- Replay regression remains the required proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/fixtures/decision_output_minimal_v1.json`
- `tests/test_decision_output_hash_v2_lock.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9x01
What changed:
- Added dev-only test scaffold `requirements-dev.txt` with `pytest` (runtime requirements unchanged).
- Added `tests/` package and pure-function header confidence tests covering:
  - `moderate` -> `medium` normalization
  - `2 medium` concerns => amber scalar
  - missing assay signals remain neutral (`Not Assessed`)

Why:
- Close the “no pytest suite” gap with a minimal, DB-free test foothold while preserving runtime dependency purity.

Determinism/Replay note:
- Dev/test-only additions; no runtime DI behavior changes.
- Replay regression remains the required proof target.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `requirements-dev.txt`
- `tests/__init__.py`
- `tests/test_molecule_header_confidence.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w114
What changed:
- Added `psi/services/molecule_sequences.py` and moved the minimal safe sequence/composition helper cluster out of `molecules.py`:
  - `_next_chain_id`
  - `_id_allocation_retry_exhausted`
  - `get_or_create_chain`
  - `_canonical_composition`
  - `composition_sha256`
- Updated `psi/services/molecules.py` to import/re-export the moved helpers and keep orchestration in place.
- Added contract smoke lock for composition-hash stability (canonical ordering + fixed digest regression).

Why:
- Complete the second structural split with minimal risk while keeping composition hashing behavior stable.

Determinism/Replay note:
- Structural split only; no intended DI output/hash changes.
- Composition hash behavior is explicitly locked by contract smoke.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_sequences.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w113
What changed:
- Replaced DI runner stderr print for invalid `PSI_DI_BASELINE_CUTOFF_ISO` with structured logging (`logger.warning(...)`) in `psi/services/di/runner.py`.
- Added module logger initialization and removed the now-unused `sys` import.

Why:
- Route runtime warnings through logging without changing DI snapshot content or replay behavior.

Determinism/Replay note:
- Diagnostics-only change; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w112
What changed:
- Hardened molecule auto-primary allocation retry failure reporting in `psi/services/molecules.py`:
  - existing bounded `IntegrityError` retry loop is preserved
  - exhaustion error now includes the last attempted primary ID candidate

Why:
- Improve clarity for concurrent-write primary ID allocation failures without changing schema or retry semantics.

Determinism/Replay note:
- Molecule CRUD-only error-path message improvement; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w111
What changed:
- Extracted shared DI runner helper `psi/services/di/runner.py::_attach_integrity_hashes(...)`.
- Replaced duplicated integrity-hash attachment logic in the two deterministic error-output return paths with the shared helper.

Why:
- Reduce duplication in DI runner error paths while preserving exact integrity metadata fields and ordering.

Determinism/Replay note:
- Refactor-only patch; DI outputs are intended to remain unchanged.
- Replay regression is the proof target for no hash-bearing output drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w110
What changed:
- Consolidated SoE v0.2/v0.3 batch+molecule builders into private `psi/services/di/soe.py::_build_soe_core(config=...)`.
- Updated public entry points to delegate:
  - `build_soe_v0_2`
  - `build_soe_v0_2_molecule`
  - `build_soe_v0_3`
  - `build_soe_v0_3_molecule`

Why:
- Complete the planned D1 SoE consolidation while reducing duplication and preserving byte-identical outputs.

Determinism/Replay note:
- Refactor-only patch; no intended DI output changes.
- Replay gate passed; any `policy_exact_match_not_found` skips remain carryover from the intentional `w108` policy package update.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/soe.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w109
What changed:
- Updated `psi/core/di/catalogs/progress_policy_v0_1.json` additively to include Roadmap v2 early milestones:
  - `expression_present`: `["expr_yield_mgL"]`
  - `purification_present`: `["purity_percent"]`
- Extended progress policy contract smoke to assert the new milestone mappings.

Why:
- Align the scientist-first progress ladder policy catalog with the approved Roadmap v2 milestone set.

Determinism/Replay note:
- Policy-as-data catalog update for UI/view-model progress display; no DI snapshot hash logic changed.
- Replay gate passed with `skipped=2`, both `reason=policy_exact_match_not_found` (carryover from the intentional w108 policy package change).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/progress_policy_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w108
What changed:
- Copied `risk_flag_severity_tiers` into `policy_body` (additive) for all `advance_to_in_vivo_*` policies and `ready_for_scaleup_screen_v0_1`.
- Updated `psi/services/di/risk_flags.py` to resolve severity tiers in deterministic order:
  1. `policy_body.risk_flag_severity_tiers`
  2. `template_structure.risk_flag_severity_tiers` (backward-compatible fallback)
- Extended contract smoke to assert the new policy-body severity tier copy is present/matches and to lock `policy_body` precedence over `template_structure`.

Why:
- Move governance semantics (risk severity tiers) into the authoritative `policy_body` surface while preserving backward compatibility for older packages.

Determinism/Replay note:
- This is an intentional governance semantics surface change for future snapshots and will change future policy semantics/package hashes for the modified policy files.
- Existing snapshot replay remains valid; if replay skips occur they are expected to be `reason=policy_exact_match_not_found` due package hash mismatch between stored snapshots and updated on-disk policy packages.
- Replay gate result for this patch: `skipped=5`, all with `reason=policy_exact_match_not_found` (allowed).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/tools/di_contract_smoke.py`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w107
What changed:
- Added deterministic header regression harness `psi/tools/molecule_header_regression.py` (stdlib-only script, no pytest dependency).
- Added dict-based fixtures covering:
  - `moderate` -> `medium` severity normalization
  - `2` medium concerns -> amber scalar
  - missing assay signals remain neutral (`Not Assessed`)

Why:
- Provide a lightweight executable regression check for the molecule scientist-header invariants after the w106 structural split.

Determinism/Replay note:
- Tooling only; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/molecule_header_regression.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w106
What changed:
- Extracted molecule scientist-header view-model builders into new module `psi/services/molecule_header.py` (progress ladder, drift/risk summary, confidence builders, header assembly).
- Updated `psi/services/molecules.py` to act as a thin coordinator and re-export/import the moved helper functions to preserve existing signatures and smoke imports.

Why:
- Reduce change risk in `molecules.py` by isolating the deterministic molecule-header logic without altering behavior.

Determinism/Replay note:
- Structural split only; header outputs are intended to remain identical (with the `w105` moderate->medium fix already in place).
- Replay regression is the proof target for no DI output/hash drift.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/services/molecule_header.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w105
What changed:
- Fixed molecule header risk severity counting to normalize `moderate` -> `medium` before bucket aggregation in `_build_molecule_header_model`.

Why:
- Prevent undercounting medium-severity risk flags in the scientist header confidence summary and avoid scalar rule misfires.

Determinism/Replay note:
- UI/view-model-only severity counting fix; no DI snapshot output/hash logic changed.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w104
What changed:
- Hardened `psi.tools.export_outcome_dataset` hash/fingerprint field extraction with deterministic stored-field fallback precedence (inputs/output policy/provenance metadata only; no recomputation).
- Export rows now reliably fill `policy_semantics_hash`, `policy_package_hash`, and `evidence_fingerprint` from stored snapshot fields when one source path is absent.
- Extended contract smoke to lock export hash-field enrichment precedence and updated operator notes to document the deterministic fallback behavior.

Why:
- Complete v2.1 outcome dataset export enrichment while preserving read-only deterministic behavior.

Determinism/Replay note:
- Export tool remains read-only and ordered by `snapshot_id ASC`; no DI compute or hash-bearing output changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/export_outcome_dataset.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w103
What changed:
- Confirmed `psi.tools.label_outcome add` already supports explicit `--outcome-event-date` (shipped earlier) and documented the operator-facing usage/examples.
- Added deterministic contract smoke coverage for `label_outcome` outcome-event-date parsing:
  - accepts valid ISO8601 and normalizes UTC `Z`
  - rejects invalid input with a stable CLI error message

Why:
- Close the operator/docs + parser-regression gap for outcome labeling date input in the v2.1 workflow.

Determinism/Replay note:
- No DI functional changes; CLI parser/docs + smoke only.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w102
What changed:
- Audited DI runner error-output paths and confirmed shared error-output construction/parity completion is already in use.
- Extended contract smoke with multi-error-factory parity assertions (`policy_schema_mismatch` and `unsupported_template`) to lock default types/nulls and enum validity.

Why:
- Finish error-output parity hardening with stronger regression coverage while preserving replay behavior.

Determinism/Replay note:
- No DI functional changes in this patch; smoke coverage only.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w101
What changed:
- Performed a docs-first sub-assessment library audit (`docs/CODE_REVIEW_w101.md`) and confirmed reproducibility/comparability paths already use shared deterministic helpers in `psi/services/di/sub_assessments.py`.
- Added a contract smoke lock for reproducibility sub-assessment helper key-shape/order stability (`reproducibility_signal_from_soe`).

Why:
- Tighten sub-assessment library guarantees without introducing replay risk from unnecessary refactors.

Determinism/Replay note:
- No DI functional code changes in this patch.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/CODE_REVIEW_w101.md`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w100
What changed:
- Added `psi/core/di/catalogs/confidence_policy_v0_2.json` with explicit component derivation mappings (QC/Reproducibility/Comparability/Interpretability) and unchanged count-only scalar rules.
- Extended confidence policy validation/loading (`psi/core/di/catalog.py`) to validate optional `component_rules` and added `load_confidence_policy_v0_2()`.
- Updated molecule-header confidence derivation to read policy-visible component labels/order/signal mappings deterministically (behavior-preserving defaults retained).
- Extended contract smoke to validate `confidence_policy_v0_2` latest-loader selection, required component-rule keys, and absence of weighted/average catalog fields.

Why:
- Expand policy-as-data coverage for confidence component derivation while preserving non-weighted deterministic behavior.

Determinism/Replay note:
- Component derivation remains deterministic and count/categorical-only; missing evidence stays neutral via existing rules.
- Replay regression passed with no skips (UI/view-model policy mapping only; DI snapshot hashes unchanged).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/confidence_policy_v0_2.json`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w99
What changed:
- Added shared deterministic heavy-compute banner text helper in `psi/services/di/util.py` and reused it in molecule header + `/di/run`.
- Moved `/di/run` heavy-compute banner outside the Scientist/Governance toggle panels so it stays visible in both modes.
- Extended contract smoke to lock shared heavy-compute banner text and deterministic DI run template panel structure.

Why:
- Keep the heavy-compute OFF/ON indicator consistently visible across scientist/governance views without affecting DI hashes.

Determinism/Replay note:
- UI/helper-only change using the existing `is_heavy_compute_enabled()` global toggle; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/di/web.py`
- `psi/services/molecules.py`
- `psi/web/templates/di/run.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w98
What changed:
- Added deterministic stage-level progress advisory selection in the molecule header view-model using the first sorted blocked DI milestone.
- Rendered a stage-level `Blocked by prerequisites` notice next to the molecule progress stage title.
- Extended contract smoke to lock deterministic stage-advisory milestone selection and plain-English blocker text prefix.

Why:
- Surface prerequisite blocking directly at the progress stage level without changing DI logic or snapshot outputs.

Determinism/Replay note:
- UI/view-model interpretation only; prerequisite advisories remain explicitly sorted and DI hashes are unchanged.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w97
What changed:
- Added explicit deterministic progress hover-text builder for the molecule header (`satisfied=` / `not_yet=` milestone keys).
- Switched the progress bar tooltip/title to prefer the new policy-key explainability text.
- Extended contract smoke to lock progress hover-text ordering and policy-key presence.

Why:
- Make progress-ladder explainability explicitly policy-key-driven and stable while keeping progress logic unchanged.

Determinism/Replay note:
- UI/view-model explainability only; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w96
What changed:
- Added deterministic drift plain-English translation helper in `psi/services/decisions.py` for DI snapshot UI rendering.
- Rendered drift translation in the DI snapshot “Run semantics” section beneath `drift_type`.
- Extended contract smoke with a deterministic drift translation fixture assertion.

Why:
- Improve scientist-first readability of drift semantics using deterministic translation (no ML / no hidden logic).

Determinism/Replay note:
- UI-only helper/rendering change; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/decisions.py`
- `psi/web/templates/decisions/_di_snapshot.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w95
What changed:
- Added Scientist/Governance view toggle to `/di/run` with localStorage persistence (`psi.di.run.view_mode`), matching the molecule-page scientist-first toggle pattern.
- Kept toggle behavior UI-only (panel visibility + button state) with explicit governance note that inputs/outputs/hashes are unaffected.
- Extended contract smoke to render `/di/run` and assert localStorage toggle presence while preserving DI form fields.

Why:
- Continue the scientist-first default view rollout while keeping governance details accessible and non-obstructive.

Determinism/Replay note:
- UI-only JS/template change; no DI compute/output/hash changes.
- Replay regression passed with no skips.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/di/run.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w94
What changed:
- Updated `psi/tools/export_outcome_dataset.py` to export top-level `outcome_event_date` and deterministic `days_to_outcome` (days from snapshot `created_at`, rounded to 6 decimals).
- Refactored the exporter into deterministic row-building / JSONL-writing helpers for easier smoke verification (read-only behavior preserved).
- Added contract smoke proof that outcome dataset row generation and JSONL output are deterministic for a fixed DB.
- Updated operator notes to document the v2.1 outcome dataset additions.

Why:
- Complete the v2.1 outcome dataset block by surfacing outcome timing metadata and derived timing deltas without affecting DI hashes.

Determinism/Replay note:
- Export tool remains read-only and deterministic (explicit ordering + stable JSONL).
- DI outputs and DI snapshot hashes remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/export_outcome_dataset.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w93
What changed:
- Added additive outcome metadata field `OutcomeLabel.outcome_event_date` (nullable) to the ORM model.
- Updated `ensure_schema()` additive column evolution to add `outcome_labels.outcome_event_date` on existing DBs without destructive migration.
- Updated `psi/services/decisions.add_outcome_label()` to accept/store `outcome_event_date` metadata.
- Updated `psi/tools/label_outcome.py` to accept optional `--outcome-event-date` (ISO8601) and display the field in `list` output.
- Included `outcome_event_date` in snapshot-detail outcome label serialization (metadata only).

Why:
- Provide the additive v2.1 outcome-event timestamp metadata needed for downstream deterministic outcome-dataset exports (`days_to_outcome` in w94).

Determinism/Replay note:
- Outcome label metadata only; DI outputs and DI snapshot hashes remain unchanged.
- Additive-only schema evolution; no destructive migration.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/decisions.py`
- `psi/tools/label_outcome.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w92
What changed:
- Extended DI contract smoke error-output parity coverage to explicitly lock v0.3 vs v0.4 parity-extension gating behavior.
- Added assertions that common happy-path top-level parity fields remain present on parity-completed error outputs and that v0.4-only fields are emitted only for v0.4 policies.
- Included a fallback-path exercise (missing `inputs_obj.evaluator_version`) in the parity gating smoke to preserve the w75 error-parity hardening guarantee.

Why:
- Finish the remaining error-output parity hardening work as a low-risk smoke/coverage patch since the shared error-output helper/consolidation is already in place.

Determinism/Replay note:
- Test-only patch; no DI compute/schema/output/hash changes.
- Replay and hash-bearing DI outputs unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w91
What changed:
- No functional SoE consolidation changes were required.
- Added `docs/CODE_REVIEW_w91.md` documenting the SoE duplication audit and why current shared-helper coverage is already sufficient.

Why:
- Patch goal was conditional; current `psi/services/di/soe.py` already centralizes core SoE logic behind shared internal builders, so a refactor would add risk without benefit.

Determinism/Replay note:
- Docs-only patch; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/CODE_REVIEW_w91.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w90
What changed:
- Added versioned UI-only confidence policy catalog `psi/core/di/catalogs/confidence_policy_v0_1.json`.
- Added deterministic confidence policy loaders/validation in `psi/core/di/catalog.py` (including `load_confidence_policy_latest()`).
- Wired molecule-header confidence scalar derivation to read scalar thresholds deterministically from the confidence policy catalog with safe fallback defaults.
- Extended contract smoke to validate confidence policy catalog presence, required keys, and latest-loader determinism.
- Updated operator notes to document the new confidence policy catalog.

Why:
- Make confidence scalar/component display rules policy-visible and versioned without changing DI outputs or hashes.

Determinism/Replay note:
- UI-only catalog consumption; no DI snapshot/hash-bearing output changes.
- Catalog latest selection is explicit and deterministic.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/confidence_policy_v0_1.json`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w89
What changed:
- Extracted count-only confidence scalar derivation into `_derive_confidence_scalar_from_components` (UI-only helper).
- Marked the molecule-header confidence scalar as optional (`scalar_optional`) and surfaced `scalar_rule_id` / `scalar_counts` for transparent UI-side rule inspection.
- Kept scalar rule deterministic and non-weighted: high concern => amber, >=2 medium concerns => amber, otherwise green/unknown.
- Added contract smoke locks for scalar rule outcomes and rejection of weighting/averaging language in the confidence surface.

Why:
- Make the confidence scalar explicitly reproducible by visible component counts and easier to audit before policy-as-data grounding.

Determinism/Replay note:
- UI/view-model helper + smoke only; no DI snapshot/hash-bearing output changes.
- No weighted scoring or averaging introduced.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w88
What changed:
- Added deterministic interpretability `detail_items` (severity tier counts ordered `high -> medium -> low -> unspecified`) to the molecule-header confidence component.
- Updated molecule header confidence UI to render interpretability severity tiers distinctly as categorical chips (display-only).
- Extended contract smoke to lock deterministic interpretability tier ordering.

Why:
- Make interpretability severity tiers visible and auditable in the confidence bar without introducing any weighting or scoring changes.

Determinism/Replay note:
- UI/view-model only change; no DI snapshot/hash-bearing output changes.
- Interpretability tier ordering is explicit and smoke-locked.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w87
What changed:
- Added a component-only confidence derivation helper (`_derive_confidence_components`) for deterministic UI-side component state checks.
- Extended contract smoke to lock component derivation determinism and neutrality for missing evidence (no penalty for absent QC/repro/comparability signals).

Why:
- Make the confidence component derivation surface explicit and testable before subsequent interpretability/scalar refinements.

Determinism/Replay note:
- UI helper + smoke only; no DI compute/output/hash changes.
- Existing scalar remains unchanged in this patch.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w86
What changed:
- Added an explicit molecule-header confidence scaffold legend clarifying `Good / Concern / Not Assessed (neutral)`.
- Added contract smoke coverage that locks the no-snapshot confidence scaffold to 4 deterministic components, all `not_assessed`.

Why:
- Make the confidence bar scaffold semantics explicit to operators/users before further component derivation refinements.

Determinism/Replay note:
- UI text + smoke only; no DI output/hash changes.
- No weighting introduced; missing evidence remains neutral.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w85
What changed:
- Surfaced latest DI risk items (key + severity tier) in the molecule scientist header, in addition to the existing severity counts.
- Added deterministic header risk-item ordering with explicit severity/key sort and neutral handling for unknown severities (`unspecified`).
- Extended contract smoke to lock molecule-header risk item ordering and neutrality semantics.

Why:
- Complete the next roadmap v2 step for scientist-first severity visibility without introducing scoring or affecting DI outputs.

Determinism/Replay note:
- UI/view-model only change; no DI snapshot/hash-bearing output changes.
- Header risk items use explicit deterministic ordering and neutral treatment for unknown severities.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w84
What changed:
- Added policy-as-data risk severity tiers under `template_structure.risk_flag_severity_tiers` across packaged DI policy files.
- Wired DI risk-flag enrichment to read policy/package severity tiers (with deterministic fallback behavior), preserving existing severities for current flags.
- Updated DI snapshot UI risk flag chips to display severity tiers distinctly (display-only, no weighting).
- Extended contract smoke with:
  - policy severity-tier coverage audit across packaged policies
  - deterministic policy-driven risk severity enrichment check
  - deterministic DI snapshot UI severity rendering check
- Updated operator notes to document policy-defined risk severity tiers.

Why:
- Complete the next roadmap v2.0c requirement by moving risk severity display semantics into policy-as-data and proving deterministic coverage/rendering.

Determinism/Replay note:
- Risk severity tier consumption is deterministic; enriched risk flags remain explicitly sorted.
- UI rendering change is display-only and does not affect DI snapshot hashes.
- Replay regression passed; package-level policy metadata changes may cause `policy_exact_match_not_found` skips for older snapshots because `policy_package_hash` changes while policy semantics remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/risk_flags.py`
- `psi/services/di/compute.py`
- `psi/web/templates/decisions/_di_snapshot.html`
- `psi/tools/di_contract_smoke.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`
- `psi/core/di/policies/advance_to_in_vivo_v0_1.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_2.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_3.json`
- `psi/core/di/policies/advance_to_in_vivo_v0_4.json`
- `psi/core/di/policies/ready_for_scaleup_screen_v0_1.json`

Gates run:
- `python -m compileall -q psi`
- `python -m psi.tools.db_schema_sanity`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`

## 2026-02-26 — v1.2.9w83
What changed:
- Added `docs/CODE_REVIEW_w83.md` as a docs-first internal checkpoint review covering patches `w75` through `w82`.
- Reviewed determinism, replay safety, policy-as-data alignment, UI-only guarantees, and hash-risk boundaries; documented findings and proof notes.
- No functional code changes were required from the review (no determinism/replay/hash-safety issues found).

Why:
- Establish a clear checkpoint record before additional roadmap work and make the audit rationale/proof easy to review.

Determinism/Replay note:
- Documentation-only patch; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/CODE_REVIEW_w83.md`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w82
What changed:
- Added operator-facing roadmap v2 implementation notes in `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`.
- Documented progress-policy and template-prerequisites catalog roles (including deterministic latest loader behavior).
- Documented experiment catalog v0.2 `resolves_risk_flags` catalog-driven risk mapping, `value_functions_enforcement_reason` enum semantics, and heavy-compute OFF-by-default hash-safety guarantees.

Why:
- Provide a concise operator reference for the roadmap v2 surfaces that are now implemented across catalogs, UI governance fields, and runtime flags.

Determinism/Replay note:
- Documentation-only patch; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/DI_ROADMAP_V2_IMPLEMENTATION_NOTES.md`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w81
What changed:
- Added read-only deterministic outcome dataset exporter `python -m psi.tools.export_outcome_dataset` (JSONL) using existing DB fields only.
- Export rows are ordered by `snapshot_id` ascending and serialized with stable JSON key ordering for reproducibility.
- Each row includes snapshot metadata plus parsed `policy_semantics_hash`, `policy_package_hash`, `evidence_fingerprint`, `decision_state`, and aggregated outcome labels (including DI review labels when present).

Why:
- Provide deterministic groundwork for closed-loop outcome analysis without schema changes or any DB writes.

Determinism/Replay note:
- Tool is read-only (`ensure=False`) and does not mutate DB state.
- Export ordering is explicit and reproducible; no DI compute/output changes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/export_outcome_dataset.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w80
What changed:
- Added explicit stable sorts (with comments) for molecule-header prerequisite status rows, blocked prerequisite advisory rows, and top-level prerequisite advisories.
- Extracted a small `_sorted_prerequisite_blockers_for_advisory()` helper to make the blocker ordering rule explicit and reusable.
- Added contract smoke determinism coverage that asserts prerequisite blocker ordering is stable regardless of input order.

Why:
- Prevent accidental UI/view-model ordering drift in scientist header lists and make deterministic ordering rules obvious in code.

Determinism/Replay note:
- UI/view-model sorting hardening only; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w79
What changed:
- Audited the molecule-header confidence model and confirmed it already uses explicit rule-based counting only (no weighted scoring) with `not_assessed` components treated neutrally.
- Added contract smoke coverage to lock non-weighted confidence behavior, deterministic component ordering, and neutral handling of missing evidence.
- Added a smoke assertion that the visible confidence rule text explicitly states the non-weighted rule.

Why:
- Prevent regressions that could reintroduce implicit weighting or treat missing evidence as negative without an explicit deterministic rule.

Determinism/Replay note:
- Test-only enforcement of existing UI-only confidence behavior; no DI compute/schema/output changes.
- Replay and hash-bearing DI outputs remain unchanged.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w78
What changed:
- Added shared helper `is_heavy_compute_enabled()` in `psi/services/di/util.py` to centralize `PSI_HEAVY_COMPUTE=1` handling with a deterministic OFF-by-default behavior.
- Switched the molecule header heavy-compute banner to use the shared helper instead of reading the environment variable inline.
- Added a visible `/di/run` UI indicator (`Heavy Compute: OFF/ON`) sourced from the shared helper and explicitly stating that DI snapshot hashes are unaffected.

Why:
- Make heavy-compute status handling consistent across UI surfaces and enforce a single OFF-by-default interpretation without affecting DI hash-bearing outputs.

Determinism/Replay note:
- UI/runtime helper only; no DI snapshot schema/output changes and no hash/replay surface changes.
- Heavy-compute indicator is display-only and does not participate in DI snapshot hashing.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/molecules.py`
- `psi/services/di/web.py`
- `psi/web/templates/di/run.html`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w77
What changed:
- Hardened the molecule-header prerequisite advisory view-model to explicitly classify blocked prerequisite templates as `missing` vs `failed` and include latest snapshot IDs when available.
- Added explicit sorting for prerequisite template keys before advisory derivation so blocker lists render deterministically.
- Updated the molecule detail template wording to show a plain-English `Blocked by prerequisites` message for structurally impossible progress claims.

Why:
- Prevent the UI from implying an impossible progress state without a deterministic, user-visible explanation of which prerequisite templates are blocking the claim.

Determinism/Replay note:
- UI/view-model only change; no DI compute or snapshot schema/output changes.
- Advisory blocker ordering is explicit and stable (sorted prerequisite template keys).

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/molecules.py`
- `psi/web/templates/molecules/detail.html`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w76
What changed:
- Added deterministic `load_template_prerequisites_latest()` catalog loader that selects the highest `template_prerequisites_vX_Y.json` version by parsed version tuple (stable tie-break by filename).
- Switched molecule header prerequisite loading to use the latest template-prerequisites catalog (current behavior unchanged because only `v0_1` exists).
- Expanded contract smoke coverage to audit progress-policy DI milestone template coverage against the prerequisites catalog, validate latest-loader determinism, and optionally validate `v0_2` loading if a `template_prerequisites_v0_2.json` file is present.

Why:
- Make template prerequisite policy-as-data expansion future-proof and ensure the molecule header cannot silently reference DI milestone templates missing from the catalog.

Determinism/Replay note:
- Catalog loading and milestone coverage checks use explicit deterministic ordering.
- No DI schema/output changes and no replay/hash-bearing compute changes.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/services/molecules.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w75
What changed:
- Hardened DI error-output parity completion to deterministically fall back to the error output engine evaluator version when `inputs_obj.evaluator_version` is absent, preserving governance/run-semantics reason generation.
- Tightened DI contract smoke parity coverage to select a representative parity-gated DI snapshot (`error_output_parity_v2_0a`) instead of any DI snapshot.
- Extended the parity smoke assertion to require `value_functions_enforcement_reason` in both representative success and synthesized error outputs when the value-functions extension gate is active.

Why:
- Ensure the w75 parity check exercises the intended new-snapshot gated path and validates governance/run-semantics parity consistently across success vs error outputs.

Determinism/Replay note:
- Error parity completion remains additive and extension-gated for new snapshots only (`error_output_parity_v2_0a`), preserving historical replay surfaces.
- No schema changes, no ranking/scoring changes, and no non-deterministic behavior introduced.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/runner.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`

## 2026-02-26 — v1.2.9w74
What changed:
- Extracted deterministic material readiness and mechanism readiness rationale helpers into shared sub-assessment utilities.
- Updated the advance-to-in-vivo template to call the new helpers without changing rationale text.
- Extended contract smoke coverage with minimal deterministic checks for the new helpers.

Why:
- Refactor for reuse across upcoming templates while preserving existing gate rationale behavior.

Determinism/Replay note:
- Refactor-only patch: no intended behavior or schema changes.
- Replay regression remains the proof target for unchanged hash-bearing outputs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/sub_assessments.py`
- `psi/services/di/templates/advance_to_in_vivo.py`
- `psi/tools/di_contract_smoke.py`

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w59
What changed:
- Expanded the existing additive `ensure_schema()` DI snapshot metadata backfill so it sets `decision_snapshots.engine_key='di'` for legacy DI rows where `engine_key` is `NULL` or empty and `schema_version LIKE 'di.%'`.
- Kept DI snapshot detection logic unchanged; the backfill makes `engine_key` authoritative for historical DI rows during schema-ensure paths.
- Documented the backfill in `MIGRATIONS.md` (idempotent, conservative, and not run in read-only replay flows that skip `ensure_schema()`).

Why it changed:
- Eliminate fallback heuristic DI snapshot detection in practice by backfilling missing `engine_key` values on historical DI snapshots.

Determinism/contract impact:
- No DI compute/ranking logic changes.
- Additive, idempotent metadata backfill only; no destructive schema changes.
- Read-only replay remains unchanged because replay flows can skip `ensure_schema()`.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w60
What changed:
- `/di/run` now supports true molecule-scope DI execution end-to-end from the web form (`scope_type=molecule` + `molecule_id`) while preserving batch-scope behavior.
- DI run form includes a scope selector (`batch`/`molecule`) with deterministic server-rendered option lists and minimal inline JS to toggle the active selector input.
- DI run context queries use explicit deterministic ordering tie-breaks for selector lists: `created_at DESC, id DESC` for both batches and molecules.
- POST handler now accepts optional `template_id`, `route`, and `study_intent` fields (if present) and stores them in `DIInput.context` without changing DI engine decision logic.

Why it changed:
- Close the remaining audit gap by enabling molecule-scope DI runs from `/di/run` rather than only batch-scope POST execution.

Determinism/contract impact:
- No DI engine compute/ranking logic changes.
- UI selection ordering is deterministic and stable.
- Replay surfaces are unchanged.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w61
What changed:
- Added additive DI output field `value_functions_enforced` for new snapshots via an explicit output-extension flag in DI inputs, keeping historical replay surfaces unchanged.
- DI snapshot UI now shows a concise **Run semantics** section (`qc_mode`, `as_of_ts`, stable-rendered `context`, `drift_type`, `state_transition`, `value_functions_enforced`).
- Extended deterministic NBE suggestions so catalog experiment suggestions can also be triggered by specific risk flags (in addition to blockers), with stable ordering and risk-flag suggestion display in the snapshot UI.

Why it changed:
- Make value-function enforcement and run semantics explicit/auditable, and broaden deterministic experiment suggestion triggers without introducing scoring.

Determinism/contract impact:
- No heuristic ranking or weighted scoring added.
- New `value_functions_enforced` field is replay-safe by explicit new-snapshot emission gating.
- NBE ordering remains deterministic (`time_tier`, `cost_tier`, `experiment_key`).

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w62
What changed:
- Added standalone deterministic fixture regression tool: `python -m psi.tools.di_fixture_regression`.
- Tool runs small DB-write-free fixture cases that validate stable ordering for gates/blockers/risk-flags/NBE suggestions and checks the `w61` `value_functions_enforced` field on DI error-path outputs.

Why it changed:
- Provide a lightweight deterministic regression harness for DI governance surfaces without introducing a heavy test framework.

Determinism/contract impact:
- Read-only/pure fixture checks only; no DI runtime behavior changes.
- No schema changes or replay surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
- `python -m psi.tools.di_fixture_regression`
## 2026-02-25 — v1.2.9w63
What changed:
- Removed truly unused local helpers from `psi/services/di/templates/advance_to_in_vivo.py` (no behavior change).
- Added clarifying comments in `psi/services/di/runner.py` documenting the intentional two-pass supersession sequence and why it preserves the single-active-snapshot invariant without changing semantics.

Why it changed:
- Governance-safe hygiene cleanup to reduce maintenance drift and make supersession behavior easier to audit.

Determinism/contract impact:
- No DI output semantics changes.
- No schema changes and no replay surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
- `python -m psi.tools.di_fixture_regression`
## 2026-02-25 — v2.0a
What changed:
- v2.0a D1 (infrastructure): refactored `psi/services/di/soe.py` to remove duplication across `build_soe_v0_2` / `build_soe_v0_3` and their molecule-scope variants using shared internal deterministic helpers (no output schema change).
- v2.0a D2 (infrastructure): consolidated DI error-output parity completion in a shared runner helper and added a contract smoke parity guard asserting representative success/error top-level key parity.
- Added policy-visible progress ladder catalog file `psi/core/di/catalogs/progress_policy_v0_1.json` plus deterministic loader/validator in `psi/core/di/catalog.py`.
- Added contract smoke validation for the progress policy catalog loader.

Why it changed:
- Establish v2.0a infrastructure groundwork from `docs/DI_MISSION_AND_ROADMAP_v2.md` while preserving deterministic replay and policy-as-data governance.

Determinism/contract impact:
- No UI/web changes in v2.0a.
- No DB schema changes.
- Replay regression remains stable; new error-output parity fields are extension-gated for new snapshots only.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w65
Naming note:
- Prior tag `v2.0a` corresponds to the w64-equivalent infrastructure-first work (SoE refactor + error parity + progress policy catalog). Human-facing patch tracking resumes at `w65+`.

What changed:
- Added a scientist-first molecule header scaffold (view-only) on molecule detail pages with a Scientist/Governance toggle (default Scientist; localStorage persisted in browser).
- Added deterministic progress bar rendering derived from `progress_policy_v0_1.json`, molecule measurement-key presence, and latest DI snapshot states (read-only view-model only).
- Added deterministic plain-English drift summary text for the latest DI snapshot drift context and a heavy-compute banner from `PSI_HEAVY_COMPUTE` (default OFF).

Why it changed:
- Begin Roadmap v2.0b scientist UX foundation without changing DI snapshot contents or hashes.

Determinism/contract impact:
- No DI snapshot compute changes and no hash-bearing DI output changes.
- View-model logic is read-only and deterministic (sorted milestones, stable snapshot ordering).

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w66
Naming note:
- Prior tag `v2.0a` corresponds to the w64-equivalent infrastructure-first work (SoE refactor + error parity + progress policy catalog). Human-facing patch tracking resumes at `w65+`.

What changed:
- Added a policy-visible template prerequisites catalog (`template_prerequisites_v0_1.json`) with deterministic loader/validator.
- Added molecule-header prerequisite advisory logic so UI progress interpretation does not claim later DI milestones when prerequisite template outcomes are missing/failed.
- Added risk severity tier scaffolding in molecule governance view (`high|medium|low|unspecified`) derived read-only from existing DI risk flags.

Why it changed:
- Implement Roadmap v2.0c structural coherence in the scientist/governance UI layer without changing DI snapshot hashes or replay behavior.

Determinism/contract impact:
- UI-only/view-model derivations are deterministic and advisory; no DI compute contract or snapshot schema changes.
- Historical policy artifacts remain unchanged; prerequisite semantics are stored in a new versioned catalog file.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w67
Naming note:
- Prior tag `v2.0a` corresponds to the w64-equivalent infrastructure-first work (SoE refactor + error parity + progress policy catalog). Human-facing patch tracking resumes at `w65+`.

What changed:
- Added a deterministic molecule-page confidence model (UI-only, render-time) with components for QC Quality, Reproducibility, Comparability, and Interpretability.
- Added a confidence bar UI in the scientist header plus visible rule text in governance view.
- Confidence summary state is derived by explicit counting rules only (no weighted scoring; missing components remain `Not Assessed`).

Why it changed:
- Implement Roadmap v2.0d confidence-bar rendering without changing DI snapshot hashes or DI engine behavior.

Determinism/contract impact:
- All confidence logic is read-only view-model derivation from existing snapshot outputs/risk flags and deterministic rules.
- No DI compute changes, no schema changes, and no replay-surface changes.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w69
What changed:
- Added `experiment_catalog_v0_2.json` (additive catalog version) with optional `resolves_risk_flags` support on experiment entries.
- Added deterministic experiment catalog validation/loader helpers, latest-version selection, and a pure risk-flag index builder (`risk_flag -> experiment_keys`).
- Added contract smoke checks for v0.2 catalog loading, latest-loader selection, and deterministic risk-flag mapping index generation.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalog.py`
- `psi/core/di/catalogs/experiment_catalog_v0_2.json`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- No DI compute/NBE behavior changes in this patch; changes are catalog/loader infrastructure only.
- Replay surfaces and snapshot hashes remain unchanged; replay regression gate verifies this.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w70
What changed:
- Updated NBE experiment suggestion planning to derive risk-flag-triggered suggestions exclusively from experiment catalog data (`resolves_risk_flags`) via the catalog mapping builder.
- Added experiment catalog v0.2 support in NBE catalog resolution, with deterministic latest-catalog fallback for forward-compatible experiment catalog refs.
- Added contract smoke assertions that NBE no longer uses a hardcoded risk->experiment map and that risk-flag suggestions remain deterministic.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/nbe.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Ordering remains deterministic (sorted risk flags, tier/cost/key sorting for experiments).
- Historical replay remains stable because v0.1 experiment catalogs simply provide empty `resolves_risk_flags`, so no extra risk-driven suggestions are invented for old snapshots.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w71
What changed:
- Added deterministic `value_functions_enforcement_reason` enum support (`active | policy_flag_off | evaluator_version_mismatch | not_applicable`) via a shared helper.
- Wired `value_functions_enforcement_reason` into DI success outputs and error outputs under the existing output-extension gating used for `value_functions_enforced`.
- Extended contract smoke to validate helper enum behavior and assert field presence in representative success/error outputs for new snapshots.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/util.py`
- `psi/services/di/compute.py`
- `psi/services/di/runner.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Field emission is extension-gated for new snapshots only (same extension gate as `value_functions_enforced`), preserving historical replay surfaces.
- No policy/schema changes and no weighted or heuristic logic introduced.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w72
What changed:
- Surfaced `value_functions_enforcement_reason` in the DI snapshot “Run semantics” governance section with a short deterministic explanation for each allowed enum value.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/web/templates/decisions/_di_snapshot.html`

Determinism/Replay note:
- UI-only template rendering change; no DI compute/output changes and no snapshot hash impact.
- Replay stability remains enforced by the replay regression gate.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-25 — v1.2.9w73
What changed:
- Extracted reusable deterministic sub-assessment helpers for comparability QC coherence summary and reproducibility-from-SoE evidence summary.
- Updated DI eval shortlisting/tie-break derivation to call the extracted helpers without changing output shape.
- Extended contract smoke shared-helper coverage to include deterministic checks for the new helpers.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/sub_assessments.py`
- `psi/services/di/eval.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Refactor-only patch: no behavior or schema changes intended.
- Replay regression gate is the proof target for unchanged hash-bearing DI outputs.

Gates run:
- `python -m compileall psi`
- `python -m psi.tools.di_contract_smoke`
- `python -m psi.tools.di_replay_regression --limit 5`
- `python -m psi.tools.db_schema_sanity`
- `./compress.sh`
## 2026-02-26 — v1.3.0a1
What changed:
- V3 additive governance foundation: added `portfolios`, `program_membership`, and `portfolio_membership` tables with explicit `sort_index` ordering.
- Added minimal deterministic portfolio CRUD services/routes/templates and portfolio detail membership management surface.
- Extended existing Program detail page with a V3 governance membership table (molecule memberships) and minimal add/sort/remove controls.
- Ordering is explicit and stable everywhere memberships are listed: `(sort_index, id)`.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/programs.py`
- `psi/services/portfolios.py`
- `psi/web/app.py`
- `psi/web/routers/programs.py`
- `psi/web/routers/portfolios.py`
- `psi/web/templates/base.html`
- `psi/web/templates/programs/detail.html`
- `psi/web/templates/portfolios/list.html`
- `psi/web/templates/portfolios/form.html`
- `psi/web/templates/portfolios/detail.html`

Determinism/Replay note:
- Additive schema + UI/service surfaces only; no DI engine or snapshot semantics changes.
- Membership ordering is explicit (`sort_index`, then row id), and DI replay outputs remain the proof target via strict gates.
## 2026-02-26 — v1.3.0a2
What changed:
- Added additive provenance tables: `actors` and `attribution_events` (single-machine actor model, deterministic local-first attribution).
- Added `psi/services/attribution.py` helper to record attribution events without DI coupling.
- Wired provenance recording for Program/Portfolio create/update and program/portfolio membership add/update/remove operations.
- Attribution remains governance-only metadata and is not used by DI computations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/attribution.py`
- `psi/services/programs.py`
- `psi/services/portfolios.py`

Determinism/Replay note:
- Additive governance metadata only; no DI output/snapshot semantics changes.
- Replay remains strict and is the acceptance proof.
## 2026-02-26 — v1.3.0a3
What changed:
- Added additive `program_rollups` governance table for deterministic persisted program rollup artifacts.
- Implemented `psi/services/program_rollups.py` with explicit `as_of` rollup builder/persistence helper using deterministic molecule enumeration and latest DI snapshot selection as-of.
- Rollup payload captures included snapshot IDs and observed policy versions/package hashes without introducing new scoring.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/program_rollups.py`

Determinism/Replay note:
- Rollups are governance artifacts derived from existing snapshots with explicit `as_of`; DI engine and snapshot semantics remain unchanged.
## 2026-02-26 — v1.3.0a4
What changed:
- Added additive `comparability_assessments` governance table (categorical-only statuses with cited keys/snapshots and policy pins).
- Added `psi/services/comparability.py` scaffold service with deterministic sorting/deduping of cited measurement keys and snapshot IDs.
- Added `psi/core/di/catalogs/comparability_policy_v0_1.json` policy-as-data scaffold with categorical status registry and placeholder rule registry.
- Extended DI contract smoke to validate comparability policy scaffold schema and deterministic cited-item ordering behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/comparability.py`
- `psi/core/di/catalogs/comparability_policy_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Categorical-only comparability scaffolding; no DI scoring or snapshot semantics changes.
## 2026-02-26 — v1.3.0a5
What changed:
- Added policy-defined deterministic ranking surface scaffold (`ranking_policy_v0_1.json`) with explicit `enabled=false` default and deterministic tie-break keys.
- Added `psi/services/v3_ranking.py` to build an explainable ranking surface only when policy enables it; disabled path returns reason trail metadata without ranking.
- Extended DI contract smoke to validate the ranking policy scaffold and deterministic disabled-by-default surface behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_1.json`
- `psi/services/v3_ranking.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Ranking surface is V3 governance scaffolding, disabled by default, and does not alter existing DI shortlisting/ranking outputs.
## 2026-02-26 — v1.3.0a6
What changed:
- Added additive `report_runs` storage table for deterministic, policy-pinned report artifacts.
- Implemented `psi/services/report_engine.py` skeleton with exactly four report types, explicit `as_of`, policy pins, snapshot coverage, fixed-section payload schemas, and deterministic validators.
- Extended DI contract smoke to lock fixed-schema deterministic payload generation for all four report types.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Report engine is a V3 governance storage/validation scaffold only; no DI computation or snapshot semantics changes.
## 2026-02-26 — v1.3.0a7
What changed:
- Implemented deterministic Molecule Report v0 generator in `psi/services/report_engine.py` using existing molecule DI snapshot outputs only (no interpretive prose, no new scoring).
- Populates fixed Molecule Report sections (identity/context, stage, confidence, mechanism, risk, gaps, drift/history, reproducibility appendix) from latest DI snapshot as-of or deterministic placeholders.
- Extended DI contract smoke with an in-memory fixture proving fixed structure and snapshot citation behavior for the molecule report generator.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Report generation reads existing snapshots only and stores deterministic report artifacts; DI engine/snapshot semantics unchanged.
## 2026-02-26 — v1.3.0a8
What changed:
- Implemented deterministic Program Report v0 generator in `psi/services/report_engine.py` with fixed sections and explicit metadata/snapshot coverage.
- Program Report reuses `a3` program rollup for molecule overview/stage surfaces and emits deterministic “not_assessed” comparability placeholders when no program comparability assessments exist.
- Extended DI contract smoke with an in-memory fixture proving rollup-backed Program Report structure, deterministic molecule ordering, and comparability placeholder behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Program Report v0 is read-only over existing snapshots/rollups and stores deterministic artifacts; DI outputs remain unchanged.
## 2026-02-26 — v1.3.0a9
What changed:
- Implemented Molecule Comparative Report v0 (2–5 molecules) in `psi/services/report_engine.py` with deterministic molecule ordering and fixed report structure.
- Added comparability citations when available, otherwise deterministic `not_assessed` placeholders.
- Integrated V3 ranking surface only through the policy-defined scaffold (disabled by default); surfaced as deterministic metadata in the report.
- Extended DI contract smoke with an in-memory fixture proving deterministic row ordering and disabled ranking surface behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Comparative report generation is read-only and policy-surfaced; no DI engine behavior changes.
## 2026-02-26 — v1.3.0a10
What changed:
- Implemented Program Comparative Report v0 (2–5 programs) in `psi/services/report_engine.py` with deterministic ordering and fixed charter-aligned section structure.
- Added ranking surface integration via the policy-defined scaffold (disabled by default) and policy-derived-only resource implications placeholder surface.
- Extended DI contract smoke with an in-memory fixture proving deterministic program ordering and resource placeholder invariants.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Comparative report generation is deterministic and read-only over existing rollup/snapshot surfaces; DI outputs unchanged.
## 2026-02-26 — v1.3.0a11
What changed:
- Added minimal deterministic V3 report UI surfaces: `/reports`, `/reports/new`, `/reports/{id}` to request and view report runs without narrative summarization.
- Added `psi/services/reports_v3.py` form/request plumbing and read-only report detail context assembly.
- Added report templates that render metadata, policy pins, snapshot coverage, and structured sections verbatim.
- Extended DI contract smoke with a deterministic template render check for the report detail surface.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/app.py`
- `psi/web/routers/reports.py`
- `psi/web/templates/base.html`
- `psi/web/templates/reports/list.html`
- `psi/web/templates/reports/new.html`
- `psi/web/templates/reports/detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- UI/report request surfaces are deterministic wrappers over persisted report artifacts and generators; no DI snapshot semantics changes.
## 2026-02-26 — v1.3.0a12
What changed:
- Added minimal deterministic lineage dashboards/services for Program and Portfolio lineage (`psi/services/lineage.py` + `/lineage/...` routes/templates).
- Lineage surfaces explicitly separate evidence changes (snapshot coverage deltas), policy changes (policy pin deltas), and governance changes (attribution events).
- Added DI contract smoke coverage for deterministic lineage service categorization output on an in-memory fixture.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/lineage.py`
- `psi/web/app.py`
- `psi/web/routers/lineage.py`
- `psi/web/templates/base.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Lineage dashboards are read-only governance surfaces over existing DB artifacts and attribution metadata; no DI semantics changes.
## 2026-02-26 — v1.3.0a13
What changed:
- Added `template_catalog_v0_1.json` scaffold for template ladder expansion governance (explicit current version + immutable version list per template).
- Added contract smoke checks for template catalog schema, deterministic ordering, and immutability guardrails against actual policy files.
- No changes to existing template semantics or DI policy resolution.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/template_catalog_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Template catalog is governance metadata only; replay semantics are unchanged and remain enforced by replay regression.
## 2026-02-26 — v1.3.0a14
What changed:
- Added additive `policy_upgrade_sessions` governance table and `psi/services/policy_upgrade.py` scaffold for deterministic policy upgrade sessions.
- Sessions record old/new policy pins, deterministic delta placeholder surfaces (ranking/comparability/report sections), and an explicit persisted operator acknowledgment flag.
- Extended DI contract smoke with in-memory coverage proving deterministic delta payloads and explicit ack persistence semantics.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`

Determinism/Replay note:
- Upgrade-session scaffolding is governance-only and does not alter active policy selection or DI snapshot semantics.
## 2026-02-26 — v1.3.0a15
What changed:
- Expanded V3 contract coverage in `di_contract_smoke` for comparability categorical-only enforcement and attribution non-interference on report payload generation.
- Added pytest coverage for deterministic fixed-schema report engine payload generation across all 4 V3 report types (`tests/test_v3_report_engine_contracts.py`).
- Updated `docs/DI_MISSION_AND_ROADMAP_V3.md` implementation-status note to reflect the actual V3 scaffolds/surfaces shipped through `a15`, including placeholder/non-assessed policy-scaffolded surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_report_engine_contracts.py`
- `docs/DI_MISSION_AND_ROADMAP_V3.md`

Determinism/Replay note:
- Contract/docs closeout only; no DI semantics or snapshot semantics changes.
## 2026-02-26 — v1.3.0a16
Intent:
- Canonicalize comparability entity pairs deterministically and add write-time governance guardrails for duplicate/conflicting pair+rule+as_of submissions.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Pair ordering is canonicalized lexicographically by `(entity_type, entity_id)` before persistence, so `(A,B)` and `(B,A)` resolve identically.
- Cited keys/snapshot ids are stored as stable/sorted JSON arrays.
- Duplicate/conflict handling emits deterministic error codes:
  - `comparability_duplicate_same_pair_rule_asof`
  - `comparability_conflict_same_pair_rule_asof`

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a48
Summary:
- Hard-deprecate V3 shortlisting policy usage by quarantining legacy shortlisting catalog as non-executable metadata and removing executable `ranking_weights` content.
- Ensure V3 report policy pins surface shortlisting as deprecated/non-executable (`allow_shortlisting=false`) for board-safe surfaces.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/shortlisting_policy_v0_1.json`
- `psi/services/reports_v3.py`
- `psi/tools/di_contract_smoke.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`21 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a49
Summary:
- Add deterministic governance tests that forbid weighted-heuristic tokens in specific DI runtime modules and the shortlisting legacy catalog.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_no_weighted_heuristics.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`22 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a50
Summary:
- Define canonical V3 Molecule Report schema builder with fixed section ordering (`I..VIII`), deterministic JSON serialization, and governance fingerprinting that explicitly excludes report timestamp.
- Wire molecule report fields to real molecule/snapshot/readiness/evidence/policy data where available.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_molecule_report_schema.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`23 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a51
Summary:
- Add canonical V3 Comparison Report schema builder with fixed `I..VIII` section ordering, metric-row/table format, stable molecule column sorting by `molecule_id`, and comparability citation/status surfaces.
- Keep comparison contract non-scored and non-weighted.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_comparison_report_schema.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`24 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a52
Summary:
- Add board-readable Jinja templates for canonical V3 molecule/comparison reports and a deterministic renderer that consumes report JSON without mutating canonical payloads.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `psi/web/templates/reports/board_molecule_v3.html`
- `psi/web/templates/reports/board_comparison_v3.html`
- `tests/test_v3_board_report_rendering.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`25 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a53
Summary:
- Add determinism tests for canonical V3 molecule/comparison reports:
  - timestamp exclusion from fingerprint
  - stable section/column ordering
  - byte-stable canonical JSON basis comparisons
  - stable non-scientific float formatting in canonical serialization

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_board_report_determinism.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`26 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a54
Summary:
- Add deterministic rule-based executive summary bullet generator for strengths/risks/decision status/required actions.
- Wire molecule and comparison report section VIII to generated bullet surfaces.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_board_reports.py`
- `tests/test_v3_executive_summary_bullets.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`27 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a55
Summary:
- Add deterministic Upgrade Delta Report skeleton under policy upgrade artifacts:
  - `header`
  - `executive_summary_bullets`
  - `change_table`
  - `appendix`
- Add board-readable HTML rendering template for upgrade delta report.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/web/templates/reports/board_upgrade_delta_v3.html`
- `psi/tools/di_contract_smoke.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a56
Summary:
- Populate deterministic `ranking_delta` section in upgrade delta appendix:
  - enabled flag changes
  - tie-break contract changes
  - criteria registry ID diffs (added/removed/unchanged)
- Keep ranking deltas ID-only with no weight/scoring fields.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a57
Summary:
- Populate deterministic `comparability_delta` in upgrade delta appendix:
  - rule registry ID diffs
  - allowed status diffs
  - gating behavior ID change status
- Keep citations/deltas as IDs/keys (no prose scoring surfaces).

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a58
Summary:
- Populate deterministic `template_catalog_delta` appendix section for upgrade deltas:
  - template key diffs
  - current version changes
  - immutable version set changes
  - prerequisite catalog ID changes

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`28 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a59
Summary:
- Enforce explicit operator acknowledgment for semantic upgrade deltas:
  - add deterministic `action_required` warning surfaces with board-visible `Action Required` label
  - add semantic-action guard (`policy_upgrade_action_required`) before report generation when unacknowledged semantic upgrades affect current pins

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/services/reports_v3.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`29 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a60
Summary:
- Formalize deterministic Template Ladder board packet/report:
  - stage list table
  - current stage
  - missing prerequisites
  - derived next actions
- Add board-readable ladder report template renderer and determinism tests.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/template_ladder_report.py`
- `psi/web/templates/reports/board_template_ladder_v3.html`
- `tests/test_template_ladder_report.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`30 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a61
Summary:
- Add fixed-schema lineage board packet surfaces for program and portfolio lineage with deterministic ordering.
- Add lineage board packet determinism tests analogous to report determinism coverage.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/lineage.py`
- `tests/test_lineage_board_packet.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS (`31 passed`)
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS (`tested=5 passed=5 failed=0 skipped=0`)
## 2026-03-02 — v1.3.0a47
Summary:
- Remove numeric weight tables from executable shortlisting ranking logic, replacing weighted score math with deterministic lexicographic tie-break ordering only.

Changed paths:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/di/shortlisting.py`

Gates run + results:
- `python -m compileall -q psi` — PASS
- `pytest -q` — PASS
- `python -m psi.tools.di_contract_smoke` — PASS
- `python -m psi.tools.di_replay_regression --limit 5` — PASS
## 2026-03-02 — v1.3.0a46
Intent:
- Document V3 hardening contracts and changelog alignment for a32-a46.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `docs/V3_HARDENING_CONTRACT_NOTES_a32_a46.md`

Determinism notes:
- Added operator-facing contract doc covering:
  - canonical serialization rules
  - ranking tie-break contract
  - comparability citation requirements
  - policy-upgrade diff artifact format
- Document is aligned to implemented code paths and tests from a32-a46.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a45
Intent:
- Surface deterministic measurement-key and evidence-snapshot citations in report detail UI for comparability/rollup context.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added deterministic citation extraction in report detail:
  - `measurement_key_citations` (sorted)
  - `evidence_snapshot_refs` (sorted)
- Extraction uses only stored report payload structures and snapshot coverage.
- UI now shows policy, rule, measurement, and evidence citation summaries in fixed positions.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a44
Intent:
- Improve scientist-facing report clarity by surfacing policy pin versions/hashes and involved rule IDs prominently in report detail UI.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/web/templates/reports/detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added deterministic `policy_pin_summary` and sorted `rule_ids` extraction in report detail service.
- UI render is strictly data-driven from stored report payload and pins; no new inference logic.
- Smoke template check now locks the presence of policy/rule summary surfaces.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a43
Intent:
- Add deterministic optional `report_fingerprint` computed from canonical report payload body.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_contracts.py`

Determinism notes:
- Added canonical SHA-256 report fingerprint generation from canonical serialized payload basis (excluding fingerprint field itself).
- Fingerprint is persisted in payload metadata only; no DI snapshot hash semantics changed.
- Added contract checks for fingerprint stability across repeated generation.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a42
Intent:
- Add explicit attribution-isolation contracts ensuring actor/attribution metadata never influences deterministic report/ranking/rollup outputs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_attribution_isolation.py`

Determinism notes:
- Added pytest contracts showing that adding attribution events does not alter:
  - program rollup outputs
  - generated program report payloads
  - ranking surfaces
- Confirms attribution remains governance metadata only, not part of deterministic computed surfaces.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a41
Intent:
- Expand replay regression harness coverage to include deterministic program rollup surface checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/tools/di_replay_regression.py`

Determinism notes:
- Replay harness now tracks program IDs in the tested snapshot slice and verifies `build_program_rollup()` is deterministic (double-run equality at fixed `as_of`).
- Rollup nondeterminism is governance-fatal and now contributes to replay failure output.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a40
Intent:
- Add upgrade-session verification routine requiring deterministic snapshot-set and input-link presence.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Determinism notes:
- Policy diff artifact now carries:
  - `snapshot_ids`
  - `deterministic_inputs`
- Added `verify_policy_upgrade_session()` with deterministic failure modes:
  - `policy_upgrade_session_missing_snapshot_set`
  - `policy_upgrade_session_missing_deterministic_inputs`
- Smoke and unit tests now validate verification success/failure paths deterministically.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a39
Intent:
- Add deterministic policy diff artifact generation for upgrade sessions with canonical hash metadata.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_policy_upgrade_diff_artifact.py`

Determinism notes:
- Added `build_policy_diff_artifact()` with stable structured payload:
  - old/new policy pins
  - old/new package and semantics hashes
  - sorted changed keys
  - deterministic nested delta surface
- `PolicyUpgradeSession.delta_payload_json` now stores this canonical diff artifact.
- Added deterministic artifact tests and updated smoke checks for new shape.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a38
Intent:
- Formalize deterministic comparability category resolution order, including explicit partial-data fallback behavior.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added `resolve_comparability_category()` with explicit policy-order precedence and stable candidate normalization.
- Added conservative deterministic fallback for partial/missing data (`not_comparable` when configured).
- `get_effective_comparability()` now returns deterministic `category_resolution` metadata.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a37
Intent:
- Enforce governance-grade comparability citations (measurement keys + snapshot IDs) and fail deterministically when absent.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Comparability creation now requires non-empty citations:
  - `cited_measurement_keys`
  - `cited_snapshot_ids`
- Added deterministic validation errors:
  - `comparability_missing_measurement_citations`
  - `comparability_missing_snapshot_citations`
- Updated smoke fixtures and added explicit missing-citation failure assertions.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a36
Intent:
- Normalize and strengthen deterministic ranking explanation trace surfaces.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_ranking.py`
- `tests/test_v3_ranking_tiebreak.py`

Determinism notes:
- `reason_trail` entries now include explicit `policy_rule_id`, `criterion_id`, `outcome`, `applied`.
- `tie_break_explanation` now includes deterministic `key_values` for configured tie-break keys.
- Added top-level `explanation_trace_version` for stable trace contract evolution.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a35
Intent:
- Formalize ranking tie-break contract in policy v0.2 and enforce deterministic tie resolution path in ranking service.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_2.json`
- `psi/services/v3_ranking.py`
- `tests/test_v3_ranking_tiebreak.py`

Determinism notes:
- Ranking tie-break now derives directly from ordered `method.tie_break_keys` in policy.
- Added explicit `tie_break_contract` policy stanza (`deterministic_only=true`, `weights_allowed=false`).
- Added tie-scenario tests that lock deterministic ranking order and explanation keys.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a34
Intent:
- Add V3 report contract tests for all four report types plus canonical serialization stability checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_report_contracts.py`

Determinism notes:
- Added contract checks for required section keys across:
  - molecule report
  - program report
  - molecule comparative report
  - program comparative report
- Added repeat-generation canonical serialization lock for identical fixture inputs.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a33
Intent:
- Formalize deterministic ordering contracts for comparative report entity rows.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_engine_contracts.py`

Determinism notes:
- Added explicit comparative ordering helpers:
  - molecule rows: `(primary_id, molecule_id, title)`
  - program rows: `(program_id)`
- Comparative report generators now call these helpers directly.
- Added unit contracts asserting stable ordering regardless of input order.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a32
Intent:
- Introduce canonical report serialization utilities for deterministic JSON string/bytes emission.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `tests/test_v3_report_engine_contracts.py`
- `pytest.ini`

Determinism notes:
- Added canonical report serialization helpers with stable dict-key ordering, explicit UTF-8 byte encoding, tuple/set normalization, and stable float formatting.
- Persisted `ReportRun` JSON fields now use canonical report serialization.
- Added byte-for-byte deterministic serialization tests.
- Added deterministic pytest discovery scoping to `tests/` to prevent artifact tree collection drift.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a31
Intent:
- Add deterministic governance red-flag surfaces to report reproducibility appendices.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Red flags are emitted as a stable, sorted list (`flag_code` ordered) inside existing `reproducibility_appendix` sections.
- Flags cover:
  - missing policy pins/hashes
  - comparability ambiguity (duplicate pair/rule candidates)
  - unacknowledged policy upgrade affecting current pins
  - ranking disabled/policy incomplete on comparative reports
- No report top-level schema keys changed.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a30
Intent:
- Add deterministic, catalog-driven Next-Best-Experiments suggestions into existing V3 report sections.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/v3_experiment_suggestions_v0_1.json`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Suggestions are sourced from versioned catalog rules with explicit `priority_order` and deterministic sort `(priority, suggestion_key, label)`.
- Suggestions include categorical priority (`high|medium|low`) and explicit reason trails only; no numeric scoring.
- Program/molecule report schemas are unchanged; suggestions are injected within existing section keys.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a29
Intent:
- Add V3 catalog immutability contract tests and additive version-surface checks.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `tests/test_v3_catalog_immutability.py`

Determinism notes:
- Locked immutable byte-level hashes for foundational V3 catalogs:
  - `template_catalog_v0_1.json`
  - `ranking_policy_v0_1.json`
  - `comparability_policy_v0_1.json`
- Added deterministic additive-version checks for ranking/comparability/template catalog file surfaces.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a28
Intent:
- Tighten lineage query scope for report and membership attribution retrieval while preserving deterministic ordering.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/lineage.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Program lineage now scopes report-run retrieval to `program_report` rows with exact serialized subject IDs.
- Program/portfolio membership attribution queries now scope to the relevant membership IDs only.
- Added smoke coverage to assert unrelated membership attribution events are excluded deterministically.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a27
Intent:
- Expand program rollup citation linkage with deterministic template/policy/snapshot coverage references.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/program_rollups.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Rollups now emit sorted citation arrays for `template_keys` and `decision_keys` in addition to snapshot/policy citations.
- Added stable `snapshot_coverage_summary` with deterministic counts.
- Contract smoke locks the citation key surface order.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a26
Intent:
- Introduce policy-driven categorical program posture derivation for rollups (no scoring) with deterministic citations.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/program_rollups.py`
- `psi/core/di/catalogs/program_posture_policy_v0_1.json`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Program posture is derived by fixed categorical rules from deterministic stage counts and molecule totals.
- Added structured rollup citations with stable key ordering (`snapshot_ids`, policy refs, molecule ids).
- Program posture policy catalog is versioned JSON and validated by contract smoke.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a25
Intent:
- Add deterministic warning surfaces for unacknowledged policy upgrades in report and lineage views.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/services/reports_v3.py`
- `psi/services/lineage.py`
- `psi/web/templates/reports/detail.html`
- `psi/web/templates/lineage/program_detail.html`
- `psi/web/templates/lineage/portfolio_detail.html`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Added `get_unacknowledged_upgrade_warnings()` with explicit ordering `(created_at DESC, id DESC)` and stable warning payload keys.
- Report detail and lineage contexts now expose deterministic governance warnings without changing report/DI semantics.
- Contract smoke validates warning presence for unacknowledged sessions and absence after explicit acknowledgement.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a24
Intent:
- Replace policy-upgrade placeholder deltas with deterministic changed-key classification and categorical impact flags.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/policy_upgrade.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Policy upgrade delta payload now emits stable top-level keys:
  - `changed_policy_keys`
  - `classification`
  - `downstream_impact_flags`
- Classification and impact flags are computed from explicit sorted changed-key sets; no probabilistic or weighted logic.
- Contract smoke locks stable key ordering and expected categorical flags.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a23
Intent:
- Stabilize attribution metadata JSON serialization and expand attribution coverage for key V3 governance actions.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/attribution.py`
- `psi/services/comparability.py`
- `psi/services/policy_upgrade.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Attribution metadata now normalizes recursively with sorted dict keys and ISO-8601 datetime/date conversion before serialization.
- New attribution events are emitted for `report_run.create`, `policy_upgrade.session.create`, `policy_upgrade.session.acknowledge`, and `comparability.assessment.create`.
- Event payload structures are stable-key dictionaries without time-based nondeterministic fields beyond explicit timestamps.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a17
Intent:
- Make comparability policy JSON authoritative for statuses/rules and scope applicability; remove hardcoded status semantics from Python.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/models.py`
- `psi/core/db.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Comparability validation now loads a cached deterministic policy object from `comparability_policy_v0_1.json`.
- `rule_id` and `status` are validated from policy data, and scope applicability uses deterministic canonical pair type ordering.
- Policy load failures and validation failures return explicit deterministic error codes.

Schema changes:
- Additive field: `comparability_assessments.policy_semantics_hash`.

Gates:
- PASS
## 2026-03-02 — v1.3.0a18
Intent:
- Add deterministic “effective comparability” resolution and governance warning surfaces over historical assessments without deleting history.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/comparability.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Effective comparability selection uses explicit `(as_of DESC, id DESC)` ordering on canonical pair and optional `rule_id`.
- History summary is deterministic (status-count map sorted by status key).
- Governance warnings are deterministic objects and ordered by stable warning key derivation.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a19
Intent:
- Introduce `ranking_policy_v0_2` with explicit lexicographic ladder semantics (policy-defined, non-weighted) while keeping ranking disabled by default.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/core/di/catalogs/ranking_policy_v0_2.json`
- `psi/services/v3_ranking.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Ranking method now reads policy-defined `criteria_order`, `outcome_precedence`, and tie-break keys.
- Enabled ranking path is lexicographic only; no hit-count heuristic and no numeric weights.
- If policy is enabled but incomplete, surface returns deterministic `policy_incomplete` with empty ranking entities.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a20
Intent:
- Harden ranking surface explainability and contract visibility (policy hashes, criterion-ordered reason trails, stable tie-break explanation), fully policy-driven.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/v3_ranking.py`
- `psi/tools/di_contract_smoke.py`

Determinism notes:
- Ranking output now includes deterministic policy hashes and tie-break explanation fields.
- Per-entity reason trails are emitted in policy criteria order.
- Contract checks assert no weight fields in ranking output and policy-order alignment.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a21
Intent:
- Remove hardcoded report policy pins and derive deterministic pin bundles from V3 catalogs.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/reports_v3.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_report_engine_contracts.py`

Determinism notes:
- Added deterministic `get_v3_report_policy_pins(report_type)` to derive template/comparability/ranking versions and hashes from catalog files.
- Pin objects are stable-key bundles and are now used by report generation form path.
- Contract and pytest tests lock pin bundle stability for report types.

Schema changes:
- None.

Gates:
- PASS
## 2026-03-02 — v1.3.0a22
Intent:
- Deepen report reproducibility appendix content under existing schema keys with deterministic governance metadata.

Changed files:
- `PATCH_NOTES.md`
- `psi/version.py`
- `psi/services/report_engine.py`
- `psi/tools/di_contract_smoke.py`
- `tests/test_v3_report_engine_contracts.py`

Determinism notes:
- Reproducibility appendix now always includes stable keys:
  - `policy_pins`
  - `catalog_versions`
  - `cited_snapshot_ids`
  - `inputs_summary`
- Keys are present across all 4 report types without changing top-level report schema keys.

Schema changes:
- None.

Gates:
- PASS
