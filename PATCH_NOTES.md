## v1.2.9w46

Why:
- Make the DI snapshot UI more audit-friendly with deterministic ordering and clearer error snapshot rendering.

What changed:
- `get_snapshot_detail` now provides `di_snapshot_ui` with pre-ordered gate outcomes, outcomes history, ranking candidates, and a unified DI error block.
- DI snapshot template uses pre-ordered lists for gate summary counts and outcomes history, renders a deterministic ranking candidates table, and surfaces a clear DI error snapshot block.

What did NOT change:
- No DI scoring/selection logic changes. No schema changes. No layout overhaul.

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
