# PSI V3 Report Layer Deep Code Review (v1.3.0a89-a93)

## Scope of Recent Changes
- `v1.3.0a89`: removed legacy `psi/services/v3_board_reports.py` shim; deprecated implementation remains quarantined under `psi/services/_deprecated/`.
- `v1.3.0a90`: improved board-first PDF/print readability (template/CSS only).
- `v1.3.0a91`: executive header readability and narrative display formatting polish (presentation-only).
- `v1.3.0a92`: measurement key rendering polish for board views (template/CSS only).
- `v1.3.0a93`: this review document.

These changes are presentation-focused and do not alter DI semantics, policy outcomes, snapshot contracts, hashing/fingerprint logic, or replay behavior.

## Current Report Architecture
- `psi/services/report_engine.py`
  - Builds canonical report payload sections from DI/runtime evidence.
  - Provides deterministic section/table ordering and canonical data surfaces.
- `psi/services/reports_v3.py`
  - Orchestrates report generation and detail retrieval.
  - Bridges persisted payloads to web-facing context.
- `psi/services/v3_narrative.py`
  - Deterministic, derived-only text layer for board readability.
  - Converts existing payload sections into headline/status/what-it-means/evidence/determinations/next-steps blocks.
- `psi/web/routers/reports.py`
  - Routes `/reports/*`, including detail rendering and export mode handling.
  - Passes board/technical view context to templates.
- `psi/web/templates/reports/*`
  - `detail.html`: container for Executive Header + Board/Technical view surfaces.
  - `_board_narrative.html`: board-first summary rendering.
  - `_technical_audit.html`: raw audit payload/policy pins/fingerprint-heavy view.
- `psi/web/static/style.css`
  - Shared UI styles; includes `pdf-mode` and `@media print` rules for stable export layout.

## PDF Export Mode Behavior
- Report detail supports export mode via query parameter (e.g., `?export=pdf`).
- In PDF mode, board presentation is emphasized and technical-heavy controls are suppressed in rendered output.
- Print styling enforces predictable spacing and wrapping:
  - break-avoid for key cards/blocks/lists,
  - fixed, readable typography tiers,
  - safer wrapping for long IDs/keys/tables.

## Determinism and Replay Invariance Touchpoints
- Deterministic ordering remains driven by report payload structure and explicit stable list handling.
- Narrative layer remains derived-only and deterministic:
  - no stochastic paths,
  - no time-dependent ordering,
  - no heuristic scoring/ranking.
- Board/technical view toggles are presentation-only and do not mutate payloads.
- Replay invariance remains guarded operationally by `psi.tools.di_replay_regression` (expected `matched=5 failed=0 skipped=0`).

## Presentation Wiring Footguns (Observed)
- Template-local data derivation can drift from payload schema over time.
  - Keep payload interpretation centralized in Python service helpers where possible.
- Jinja accumulation/conditional fallback logic can produce "missing" even when data exists in alternate sections.
  - Prefer precomputed display strings in route/service context for critical header fields.
- Rendering large raw structures in board-facing sections increases noise and causes PDF overflow.
  - Keep raw JSON confined to technical/audit view.
- Re-sorting arrays in templates can unintentionally diverge from canonical engine ordering.
  - Render payload array order as-is unless a deterministic sort contract is explicitly defined upstream.

## Next Safe Steps (Ideas Only)
1. Add a small report-view model helper in `reports_v3.py` that prepares all executive-header display fields consistently across report types.
2. Add lightweight snapshot/template render tests for key board sections (identity header, measurement keys, determination cards) to prevent regressions in template wiring.
3. Consolidate print-safe utility classes for report blocks into a narrow CSS namespace to reduce accidental style collisions.
4. Keep deprecated surfaces physically isolated and avoid importing them outside explicitly skipped legacy tests.
5. Maintain a short "board vs technical" rendering checklist in contributor docs to prevent future hash/payload leakage into board view.
