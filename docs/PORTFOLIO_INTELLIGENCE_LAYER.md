# Portfolio Intelligence Layer

Version: v1.3.0c60

## Purpose

The Portfolio Intelligence Layer is a leadership-facing read-model that summarizes execution and evidence posture across PSI programs.

It answers:
- Which programs are progressing?
- Which programs are blocked?
- Where are tasks accumulating?
- Which molecules are closest to readiness?
- Where are evidence gaps across the portfolio?

## Data Sources (Read-Only)

Portfolio views are derived from existing persisted PSI entities:
- `Program`
- `Molecule`
- `DecisionSnapshot`
- `ExperimentTask`
- `DataRecord`
- InsightEngine-derived interpretation (`build_insight_bundle`)

## Boundaries

The portfolio layer must remain additive and read-only:
- No DI semantic changes.
- No writes to DecisionSnapshot payloads.
- No portfolio state embedded in snapshots.
- No fake evidence object creation.
- No duplication of ExperimentTask lifecycle state.
- No board-cache source-of-truth behavior.

## Service Surfaces

Primary service module: `psi/services/portfolio.py`

Key functions:
- `build_portfolio_summary`
- `build_program_portfolio_summary`
- `build_portfolio_program_summaries`
- `build_molecule_leaderboard`
- `build_evidence_gap_report`
- `build_portfolio_timeline`
- `build_portfolio_export_rows`

These are deterministic and rely on stable ordering for leadership reporting.

## Web Surfaces

Routes:
- `GET /portfolio` (overview)
- `GET /portfolio/export` (CSV)

Template:
- `psi/web/templates/portfolio/overview.html`

## Regression Guarantees

Tests cover:
- Deterministic portfolio summary behavior.
- No mutation of DI snapshot state from portfolio reads.
- No regression in development board grouping behavior caused by portfolio queries.
- Task-to-DataRecord linking remains intact.
- Export and timeline metrics remain deterministic.
