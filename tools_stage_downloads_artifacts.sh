#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d_%H%M%S)"
INBOX=~/psi_codex/_artifacts/INBOX/from_Downloads/$TS
mkdir -p "$INBOX"

mv -n ~/Downloads/psi_overlay_* "$INBOX"/ 2>/dev/null || true
mv -n ~/Downloads/psi_patch_*    "$INBOX"/ 2>/dev/null || true
mv -n ~/Downloads/psi_code_snapshot_* "$INBOX"/ 2>/dev/null || true
mv -n ~/Downloads/psi_debug_* "$INBOX"/ 2>/dev/null || true
mv -n ~/Downloads/psi_repo_*_code_only.zip "$INBOX"/ 2>/dev/null || true
mv -n ~/Downloads/psi_*review*.docx "$INBOX"/ 2>/dev/null || true

echo "$INBOX"
