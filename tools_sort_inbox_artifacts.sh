#!/usr/bin/env bash
set -euo pipefail

INBOX="${1:-}"
if [[ -z "$INBOX" ]]; then
  echo "Usage: $0 /path/to/_artifacts/INBOX/from_Downloads/<timestamp>"
  exit 2
fi
if [[ ! -d "$INBOX" ]]; then
  echo "ERROR: INBOX does not exist: $INBOX" >&2
  exit 2
fi

ART=~/psi_codex/_artifacts

mkdir -p \
  "$ART/overlays"/{v1.2.9,v1.3.0,v2.0,other} \
  "$ART/patches"/{v1.2.9,v1.3.0,v2.0,other} \
  "$ART/snapshots"/{v1.2.9,v1.3.0,v2.0,other} \
  "$ART/debug"/{v1.2.9,v1.3.0,v2.0,other} \
  "$ART/repo_code_only"/{v1.2.9,v1.3.0,v2.0,other} \
  "$ART/reviews" "$ART/misc"

move_glob () {
  local glob="$1"
  local dest="$2"
  shopt -s nullglob
  local items=( $glob )
  shopt -u nullglob
  if (( ${#items[@]} > 0 )); then
    mv -n "${items[@]}" "$dest"/
  fi
}

echo "Sorting from: $INBOX"

# Reviews
move_glob "$INBOX"/psi_*review*.docx "$ART/reviews"

# Overlays (directories)
move_glob "$INBOX"/psi_overlay_v1.2.9* "$ART/overlays/v1.2.9"
move_glob "$INBOX"/psi_overlay_v1.3.0* "$ART/overlays/v1.3.0"
move_glob "$INBOX"/psi_overlay_v2.0*   "$ART/overlays/v2.0"
move_glob "$INBOX"/psi_overlay_*       "$ART/overlays/other"

# Patches (dirs + zips)
move_glob "$INBOX"/psi_patch_v1.2.9* "$ART/patches/v1.2.9"
move_glob "$INBOX"/psi_patch_v1.3.0* "$ART/patches/v1.3.0"
move_glob "$INBOX"/psi_patch_v2.0*   "$ART/patches/v2.0"
move_glob "$INBOX"/psi_patch_*       "$ART/patches/other"

# Snapshots (zips)
move_glob "$INBOX"/psi_code_snapshot_v1.2.9* "$ART/snapshots/v1.2.9"
move_glob "$INBOX"/psi_code_snapshot_v1.3.0* "$ART/snapshots/v1.3.0"
move_glob "$INBOX"/psi_code_snapshot_v2.0*   "$ART/snapshots/v2.0"
move_glob "$INBOX"/psi_code_snapshot_*       "$ART/snapshots/other"

# Debug (zips)
move_glob "$INBOX"/psi_debug_v1.2.9* "$ART/debug/v1.2.9"
move_glob "$INBOX"/psi_debug_v1.3.0* "$ART/debug/v1.3.0"
move_glob "$INBOX"/psi_debug_v2.0*   "$ART/debug/v2.0"
move_glob "$INBOX"/psi_debug_*       "$ART/debug/other"

# Repo code-only (zips)
move_glob "$INBOX"/psi_repo_v1.2.9* "$ART/repo_code_only/v1.2.9"
move_glob "$INBOX"/psi_repo_v1.3.0* "$ART/repo_code_only/v1.3.0"
move_glob "$INBOX"/psi_repo_v2.0*   "$ART/repo_code_only/v2.0"
move_glob "$INBOX"/psi_repo_*       "$ART/repo_code_only/other"

# Anything else -> misc
shopt -s nullglob
left=( "$INBOX"/* )
shopt -u nullglob
if (( ${#left[@]} > 0 )); then
  mv -n "${left[@]}" "$ART/misc"/
fi

echo "Done."
