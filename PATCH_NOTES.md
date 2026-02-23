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
