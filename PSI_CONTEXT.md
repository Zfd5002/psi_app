# PSI_CONTEXT.md
Purpose: Continuity + Context for ZIP-based PSI Development

This file exists to preserve **critical architectural, dependency, and workflow context**
when PSI is shared as a **code-only ZIP** (with large or external components removed).

It is written primarily for:
- ChatGPT / AI assistants helping develop PSI
- The project maintainer (future me)
- Any trusted collaborator reviewing the repo offline

This file is **not user-facing documentation** and should remain in the repo root.

---

## 1. What PSI Is (High-level)

PSI (Preclinical Systems Intelligence) is a **local-first scientific application**
built for biologics R&D.

Core goals:
- Store biologic sequences (antibodies, fusions, etc.)
- Compute deterministic annotations and predictions
- Attach structured **experimental data** (batch-first)
- Serve as a long-term foundation for **AI/ML applications**

Stack:
- Python
- FastAPI
- Jinja2 templates
- SQLite (local)
- No React/Vue
- No background jobs or async pipelines
- Deterministic rendering only

---

## 2. ZIP Overlay Workflow (Critical)

PSI is developed and shared via **ZIP overlay updates**, not git patches.

Rules:
- ZIPs are **code-only**
- ZIPs are applied via `rsync` or file overlay
- ZIPs must NEVER include:
  - `.git/`
  - `.venv/`
  - SQLite DB files (`*.db`, `*.sqlite`)
  - uploads/
  - caches or artifacts

Expected workflow:
1. User unzips overlay into a staging directory
2. User overlays onto existing local repo using `rsync`
3. Local DB, venv, and uploads persist untouched

Desktop shortcut note:
- If you need to (re)install the desktop shortcut, run the installer **only** from `~/psi_repo` (runtime repo).
- Do **not** install the shortcut from `~/psi_codex` (patch builder), or it will repoint the launcher to the wrong path.

This is **intentional** and fundamental to PSI’s design.

### Release checklist (REQUIRED for every overlay ZIP)

1) **Version bump**: update the canonical version constant in `psi/version.py`:
   - `PSI_VERSION = "vX.Y.Z..."`
   - Verify with: `python -m psi.tools.print_version`
2) **Patch notes append-only**: add a new entry to `PATCH_NOTES.md` (never edit older entries).
3) Run:
   - `python -m psi.scripts.smoke_test`
   - `./scripts/start_psi.sh` (manual sanity: canonical user launch; homepage loads)
4) Build code-only overlay ZIP using `compress.sh` and verify it contains only changed files.

Note: `smoke_test` enforces that `PATCH_NOTES.md` contains the current `PSI_VERSION`.

---

## 3. ANARCI (Important: intentionally missing from ZIPs)

ANARCI is a **vendored third-party dependency** used for:
- Antibody numbering
- Variable domain identification
- IMGT-style residue mapping

Key points:
- ANARCI lives at: `vendor/anarci/`
- It is intentionally **excluded from overlay ZIPs** (packaging hygiene)
- When missing, treat ANARCI as a **black box dependency**

Assumptions when ANARCI is not present:
- PSI code that *calls* ANARCI is correct
- Numbering outputs are deterministic
- No changes are being made to ANARCI internals unless explicitly stated

If ANARCI needs to be restored:
- Rehydrate from the upstream source or local vendor copy
- No schema or UI logic should depend on ANARCI internals

Unless debugging ANARCI itself, its absence is **non-blocking**.

---

## 4. Local Environment Assumptions

The following always exist **locally** but are not shared in ZIPs:

- Python virtual environment: `.venv/`
- SQLite database(s)
- Uploaded experimental files
- Local caches

The app is expected to:
- Create tables on startup (`ensure_schema`)
- Gracefully handle existing data
- Never require a clean DB unless explicitly stated

---

## 5. Batch-first Experimental Data Model (Design Contract)

Experimental data in PSI is **batch-first**, not molecule-first.

Identifier format:
- Molecule code: `TCB001`
- Batch code: `TCB001-001`, `TCB001-002`, etc.
- Regex: `^[A-Z0-9]+-\d{3}$`

Experimental data attaches to:
- Batch → AssayRun → Files

Initial assay types (v1.1.5):
- SEC-HPLC
- BLI / SPR
- Endotoxin

Assay data is stored as:
- `payload_json` (full structured record)
- `summary_json` (key metrics for UI + AI)

This structure is intentional and should not be flattened.

---

## 6. Viewer v2 + Annotation System (Context)

Sequence viewing uses **Viewer v2**, which supports:
- Native text selection
- Deterministic residue spans
- Highlighting via `data-start` / `data-end`
- Clipboard sanitization (AA-only)

Annotations:
- Use span-only wiring (no JSON blobs in HTML)
- Are presentation-only in some contexts
- Must never break wrapping or selection behavior

---

## 7. Versioning Philosophy

PSI uses **semantic-ish versions**, but with emphasis on:
- Additive changes
- No destructive migrations
- Backward compatibility with local data

Examples:
- v1.1.4 → Viewer + annotation wiring fixes
- v1.1.5 → Batch-first experimental data foundation

### Version invariants (CANONICAL)

The PSI version constant is defined **only** in:
- `psi/version.py` as `PSI_VERSION`

Any documentation or instructions that reference bumping the version anywhere else
(including `psi/web/app.py`) are **incorrect**.

Verification:
- `python -m psi.tools.print_version`

Code rule:
- All tools, UI footers, smoke tests, and scripts must import `PSI_VERSION` from `psi.version`.

### Legacy YAML Engine Deprecation Clock (Intent Only)

- Target: **v1.3.0** makes DI the default for new decision runs (soft policy; not enforced here).
- Legacy YAML remains **read-only** for rendering historical snapshots.
- UI should display a **“Legacy YAML engine”** warning badge where legacy snapshots render (intent only).

---

## 8. How to Read a ZIP Without Missing Pieces

If something appears missing in a ZIP:
1. Check whether it is intentionally excluded
2. Consult this file
3. Assume local-first design unless stated otherwise

When in doubt:
- Ask whether a component is **vendored**, **generated**, or **local-only**

---

## 9. Editing This File

This file is expected to:
- Grow over time
- Be edited as architecture evolves
- Stay high-signal and concise

Do NOT remove it during compression.
It exists specifically so context survives compression.

---

End of PSI_CONTEXT.md
## Developer convenience scripts

### Build a code-only ZIP (auto-versioned)
From the repo root:

- `./compress.sh`

This auto-detects the current PSI version from `psi/version.py` (`PSI_VERSION`) and writes a ZIP to `~/Downloads/` named:
- `psi_repo_<PSI_VERSION>_code_only.zip`

### Install a desktop shortcut (Ubuntu/Linux)
From the repo root:

- `bash scripts/install_desktop_shortcut.sh`

This creates `~/Desktop/PSI.desktop` that launches:
- `scripts/start_psi.sh` (canonical user launch contract; no reload by default)

If your desktop environment blocks launching, right-click the icon and choose **Allow Launching**.

## Release helper
- To bump the UI footer version and append PATCH_NOTES stub:
  python -m psi.scripts.bump_version v1.2.4a

---

## Version governance (permanent rule)

- `psi/version.py` is the **only allowed location** where the PSI version string is defined.
- No other file may hardcode a PSI version literal.
- All tools, UI footers, smoke tests, and scripts must import `PSI_VERSION` from `psi.version`.
- Version changes must modify **only** `psi/version.py` (docs like PATCH_NOTES remain append-only).

---

## 10. DI Mission & Roadmap (Authoritative)

The authoritative PSI Decision Intelligence (DI) Mission & Roadmap is stored in-repo at:

- `docs/DI_MISSION_AND_ROADMAP.docx`

Future DI work must treat that document as the source of truth for:
- DI mission statement
- roadmap phases / version intent
- scope creep boundaries

This file is intentionally included in code-only overlay ZIPs.

### DI snapshot integrity invariant (governance)

- Snapshot integrity hashes are computed over **portable** payloads only.
- Machine-local debug metadata (e.g. `inputs_json.policy_path`) MUST NOT contribute to integrity hashing.
