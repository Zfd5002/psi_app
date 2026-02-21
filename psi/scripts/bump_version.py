"""PSI release helper: bump PSI_VERSION and append PATCH_NOTES entry.

Run:
  python -m psi.scripts.bump_version v1.2.3d

Behavior:
  - Updates PSI_VERSION in psi/version.py (single canonical source of truth)
  - Appends a new stub section to PATCH_NOTES.md (append-only discipline)
  - Prints a short checklist of next commands

Constraints:
  - No DB changes
  - Deterministic edits (single-line replacement + append-only)
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    version_py: Path
    patch_notes: Path


def _paths() -> Paths:
    repo_root = Path(__file__).resolve().parents[2]
    return Paths(
        repo_root=repo_root,
        version_py=repo_root / "psi" / "version.py",
        patch_notes=repo_root / "PATCH_NOTES.md",
    )


_VERSION_RE = re.compile(r"^v\d+\.\d+\.\d+[A-Za-z0-9._-]*$")


def _validate_version(v: str) -> None:
    if not _VERSION_RE.match(v.strip()):
        raise SystemExit(
            f"Invalid version '{v}'. Expected something like v1.2.3d (must start with 'v')."
        )


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")


def _bump_version_py(version_py: Path, new_version: str) -> tuple[str, str]:
    """Replace PSI_VERSION constant in psi/version.py.

    Returns: (old_version, new_contents)
    """

    src = _read_text(version_py)

    # Example line:
    # PSI_VERSION = "v1.2.3c"
    pat = re.compile(r'^(PSI_VERSION\s*=\s*")(?P<v>v[^\"]+)("\s*)$', flags=re.M)
    m = pat.search(src)
    if not m:
        raise SystemExit(
            f"Could not find PSI_VERSION constant in {version_py}. Expected: PSI_VERSION = \"v...\""
        )
    old_version = m.group("v")
    if old_version == new_version:
        return old_version, src

    new_src = pat.sub(r"\1" + new_version + r"\3", src, count=1)
    return old_version, new_src


def _patch_notes_has_header(patch_notes_text: str, version: str) -> bool:
    return re.search(rf"^##\s+\d{{4}}-\d{{2}}-\d{{2}}\s+—\s+{re.escape(version)}\s*$", patch_notes_text, re.M) is not None


def _append_patch_notes(patch_notes: Path, version: str) -> bool:
    """Append a new patch-notes stub. Returns True if appended."""
    txt = _read_text(patch_notes)
    if _patch_notes_has_header(txt, version):
        return False

    today = date.today().isoformat()
    stub = (
        "\n"
        f"## {today} — {version}\n"
        "- Packaging: harden overlay ZIP exclusions (vendor/caches)\n"
        "- Release: add bump_version helper + smoke_test guardrail\n"
        "- UI: molecule-scoped <details> persistence + batch expand/collapse\n"
    )

    # Ensure file ends with a newline before appending.
    if not txt.endswith("\n"):
        txt += "\n"
    txt += stub
    _write_text(patch_notes, txt)
    return True


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__.strip())
        raise SystemExit(0)

    new_version = argv[0].strip()
    _validate_version(new_version)

    paths = _paths()
    if not paths.version_py.exists():
        raise SystemExit(f"Missing {paths.version_py}")
    if not paths.patch_notes.exists():
        raise SystemExit(f"Missing {paths.patch_notes}")

    old_version, new_src = _bump_version_py(paths.version_py, new_version)
    if old_version == new_version:
        print(f"PSI_VERSION already set to {new_version} in psi/version.py")
    else:
        _write_text(paths.version_py, new_src)
        print(f"Updated PSI_VERSION: {old_version} -> {new_version}")

    appended = _append_patch_notes(paths.patch_notes, new_version)
    if appended:
        print(f"Appended PATCH_NOTES.md entry for {new_version}")
    else:
        print(f"PATCH_NOTES.md already contains a header for {new_version} (no changes)")

    print(
        "\nNext:\n"
        "  python -m psi.tools.print_version\n"
        "  python -m psi.scripts.smoke_test\n"
        "  ./scripts/start_psi.sh --prod\n"
        "  ./compress.sh\n"
    )


if __name__ == "__main__":
    main()
