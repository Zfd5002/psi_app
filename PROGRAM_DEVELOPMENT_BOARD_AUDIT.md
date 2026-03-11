# Program Development Board Audit

## 1. Board Architecture

### Route and template path
- Route: `GET /programs/{program_id}/board` in [`psi/web/routers/programs.py`](./psi/web/routers/programs.py)
- Handler: `program_development_board(...)`
- Template: [`psi/web/templates/programs/board.html`](./psi/web/templates/programs/board.html)

### Board model source
The route does **not** build board state inline. It calls:

```python
board = dev_board_svc.build_development_board(db, program_id=int(program_id))
```

Source: [`psi/web/routers/programs.py:120`](./psi/web/routers/programs.py)

The board builder is:
- `psi.services.dev_board.build_development_board(...)`
- Source file: [`psi/services/dev_board.py`](./psi/services/dev_board.py)

### Rendered columns
The template renders four board groups exactly:
- `READY` -> `g.ready`
- `FAILED CRITERIA` -> `g.failed`
- `MISSING DATA` -> `g.missing_data`
- `NOT EVALUATED` -> `g.not_evaluated`

Source: [`psi/web/templates/programs/board.html:144-146`](./psi/web/templates/programs/board.html:144), [`:219-221`](./psi/web/templates/programs/board.html:219), [`:294-296`](./psi/web/templates/programs/board.html:294), [`:369-371`](./psi/web/templates/programs/board.html:369)

---

## 2. Source of Board Status

### Status data origin
For each molecule in the program, the board loads the **latest** `DecisionSnapshot` for that molecule:

```python
snapshots = (
    db.query(DecisionSnapshot)
    .filter(DecisionSnapshot.program_id == program_id_i)
    .order_by(DecisionSnapshot.molecule_id.asc(), DecisionSnapshot.created_at.desc(), DecisionSnapshot.id.desc())
    .all()
)
# first snapshot per molecule_id becomes "latest"
```

Source: [`psi/services/dev_board.py:296-309`](./psi/services/dev_board.py:296)

Then it parses `snap.outputs_json`, builds an insight bundle, and reads:
- `molecule_status`
- `missing_evidence` (missing metrics)

```python
output = _safe_json_dict(snap.outputs_json if snap is not None else None)
bundle = build_insight_bundle(output if output else None)
missing = [x for x in (bundle.get("missing_evidence") or []) if isinstance(x, dict)]
status = str(bundle.get("molecule_status") or "not_assessed")
```

Source: [`psi/services/dev_board.py:324-329`](./psi/services/dev_board.py:324)

### DB fields effectively used for grouping
- `DecisionSnapshot.program_id`
- `DecisionSnapshot.molecule_id`
- `DecisionSnapshot.created_at`
- `DecisionSnapshot.id`
- `DecisionSnapshot.outputs_json`

Molecule rows are sourced from `Molecule.program_id` and grouped by molecule id.

---

## 3. Logic for Each Column

Column assignment is centralized in `_group_key(...)`:

```python
def _group_key(*, has_snapshot: bool, status: str, missing_count: int) -> str:
    if not has_snapshot:
        return "not_evaluated"
    st = str(status or "").strip().lower()
    if st in {"ready", "pass", "approved"}:
        return "ready"
    if missing_count > 0:
        return "missing_data"
    if st in {"blocked", "fail", "failed", "not_ready", "hold"}:
        return "failed"
    return "not_evaluated"
```

Source: [`psi/services/dev_board.py:35-45`](./psi/services/dev_board.py:35)

Interpretation by column:
- **Ready**: snapshot exists and `molecule_status` is one of `ready/pass/approved`
- **Failed Criteria**: snapshot exists, no missing metrics, and status is one of `blocked/fail/failed/not_ready/hold`
- **Missing Data**: snapshot exists and `missing_evidence` has one or more metrics
- **Not Evaluated**: no snapshot exists, or snapshot status is outside the recognized ready/failed sets while not flagged missing

The UI’s “Why here” explanation is also DI/snapshot-driven; for no snapshot it explicitly says:

```python
"Not evaluated because no DI snapshot exists."
```

Source: [`psi/services/dev_board.py:133-152`](./psi/services/dev_board.py:133)

---

## 4. Conditions Producing "Not Evaluated"

`Not Evaluated` is produced in two code paths:

1. **No decision snapshot for the molecule**
- `_group_key(... has_snapshot=False ...) -> not_evaluated`
- `_why_here(...)` text: `Not evaluated because no DI snapshot exists.`

2. **Snapshot exists but status is unrecognized**
- If status is not in ready set, missing_count is 0, and status is not in failed set, `_group_key` falls through to `not_evaluated`.

Source: [`psi/services/dev_board.py:35-45`](./psi/services/dev_board.py:35), [`:133-152`](./psi/services/dev_board.py:133)

### Does board status depend on DI evaluation?
Yes. In practice, evaluated board states depend on having a `DecisionSnapshot.outputs_json` interpreted by `build_insight_bundle(...)`.

### Does entering experimental data alone trigger board evaluation?
No board code triggers DI execution on data entry. The board reads existing snapshots only.

### What action triggers evaluation?
DI execution is triggered through the DI run flow:
- `GET /di/run` (form)
- `POST /di/run` -> calls `run_di(...)` and redirects to `/decisions/{snap_id}`

Source: [`psi/web/routers/di.py:17-38`](./psi/web/routers/di.py:17), [`:107-121`](./psi/web/routers/di.py:107)

---

## 5. Whether Tutorial Phase 4 Expectations Are Correct

Based on code behavior:

- If Phase 4 expects board columns to reflect molecule readiness/blockers **without** running DI, that expectation is not code-aligned.
- If tutorial molecules have data but no DI snapshot yet, they will appear under **Not Evaluated**.
- To see molecules move into **Ready / Failed Criteria / Missing Data**, DI must be run for the relevant scope so snapshots exist.

The board is therefore a **DI snapshot interpretation surface**, not a pure “data entered implies evaluated” surface.

---

## Final Statement

**Based on the code, the Program Development Board represents the latest DI-derived molecule evaluation state (from DecisionSnapshot outputs), grouped into ready/failed/missing/not-evaluated buckets rather than raw experimental-data presence alone.**
