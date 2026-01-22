#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/update.zip"
  exit 1
fi

ZIP="$1"
if [[ ! -f "$ZIP" ]]; then
  echo "Error: zip not found: $ZIP"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP_BASE="${HOME}/psi_updates"
STAMP="$(date +%Y%m%d_%H%M%S)"
TMP_DIR="${TMP_BASE}/update_${STAMP}"

mkdir -p "$TMP_DIR"
echo "Unzipping to: $TMP_DIR"
unzip -q "$ZIP" -d "$TMP_DIR"

# Determine source root (either contains psi_repo_refactored/ wrapper or is root itself)
SRC=""
if [[ -d "$TMP_DIR/psi_repo_refactored" ]]; then
  SRC="$TMP_DIR/psi_repo_refactored/"
else
  SRC="$TMP_DIR/"
fi

echo "Rsync overlay from: $SRC"
echo "Into repo: $REPO_ROOT"
rsync -av --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='psi/psi.sqlite' \
  --exclude='*.sqlite' \
  --exclude='*.sqlite3' \
  --exclude='*.db' \
  --exclude='scripts/' \
  "$SRC" "$REPO_ROOT/"
echo "Done. Now run:"
echo "  cd $REPO_ROOT && git status"
