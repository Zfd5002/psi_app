#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------
# PSI code-only ZIP builder
# ----------------------------------------
#
# Usage:
#   ./compress.sh                       # auto-detect version, build zip only
#   ./compress.sh v1.2.3                # override version tag
#   ./compress.sh --install-shortcut    # build zip + install desktop shortcut
#   INSTALL_SHORTCUT=1 ./compress.sh    # build zip + install desktop shortcut
#
# Notes:
# - Version is sourced from psi/version.py (PSI_VERSION = "vX.Y.Z")
# - Desktop shortcut install is opt-in and safe to re-run.
#

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# --- arg parsing ---
VERSION_OVERRIDE=""
INSTALL_DESKTOP=0

for arg in "$@"; do
  case "$arg" in
    --install-shortcut)
      INSTALL_DESKTOP=1
      ;;
    --no-desktop)
      INSTALL_DESKTOP=0
      ;;
    v*)
      # allow a single version override like "v1.2.3"
      VERSION_OVERRIDE="$arg"
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: ./compress.sh [vX.Y.Z] [--install-shortcut|--no-desktop]"
      exit 2
      ;;
  esac
done

if [ "${INSTALL_SHORTCUT:-0}" = "1" ]; then
  INSTALL_DESKTOP=1
fi

# --- detect version from source of truth ---
detect_version() {
  local version_py="$REPO_ROOT/psi/version.py"
  if [ ! -f "$version_py" ]; then
    return 1
  fi
  # Extract PSI_VERSION from the canonical constant
  # Example line:
  # PSI_VERSION = "v1.2.1"
  local v
  v="$(grep -Eo '^PSI_VERSION[[:space:]]*=[[:space:]]*"v[^"]+"' "$version_py" | head -n 1 | sed -E 's/.*"((v[^"]+))".*/\1/')"
  if [ -n "${v:-}" ]; then
    echo "$v"
    return 0
  fi
  return 1
}

VERSION=""
if [ -n "${VERSION_OVERRIDE:-}" ]; then
  VERSION="$VERSION_OVERRIDE"
else
  if VERSION="$(detect_version)"; then
    :
  else
    echo "⚠️  WARNING: Could not auto-detect PSI_VERSION from psi/version.py"
    VERSION="unknown"
  fi
fi

ZIP="$HOME/Downloads/psi_repo_${VERSION}_code_only.zip"

echo "📦 Building PSI code-only ZIP"
echo "Repo: $REPO_ROOT"
echo "Output: $ZIP"
echo "Version tag: $VERSION"
echo

# Remove existing zip if present
if [ -f "$ZIP" ]; then
  echo "⚠️  Removing existing ZIP"
  rm -f "$ZIP"
fi

# Create ZIP
zip -r "$ZIP" . \
  -x ".git" \
  -x ".git/*" \
  -x ".venv/*" \
  -x "vendor/*" \
  -x "vendor/**" \
  -x "uploads/*" \
  -x "psi/uploads/*" \
  -x "*.sqlite" -x "*.db" \
  -x "*.sqlite-wal" -x "*.sqlite-shm" -x "*.sqlite-journal" \
  -x "__pycache__/*" -x "**/__pycache__/*" \
  -x "*.pyc" -x "*.pyo" \
  -x ".pytest_cache/*" -x ".mypy_cache/*" -x ".ruff_cache/*" \
  -x "*.bak" -x "*.bak~" -x "*.bak*" \
  -x "PSI_ENVIRONMENT.md" \
  -x "psi/web/templates/molecules/*.bak_*"

echo
echo "✅ ZIP created successfully"
ls -lh "$ZIP"

echo
echo "🔍 Verifying exclusions..."
if zipinfo -1 "$ZIP" | egrep -i '((^|/)\.git(/|$)|\.venv/|vendor/|uploads/|\.sqlite$|\.db$|\.sqlite-(wal|shm)$|\.sqlite-journal$|__pycache__/|\.pyc$|\.bak(~|$|_))' >/dev/null; then
  echo "❌ ERROR: Forbidden files detected in ZIP"
  zipinfo -1 "$ZIP" | egrep -i '((^|/)\.git(/|$)|\.venv/|vendor/|uploads/|\.sqlite$|\.db$|\.sqlite-(wal|shm)$|\.sqlite-journal$|__pycache__/|\.pyc$|\.bak(~|$|_))'
  exit 1
else
  echo "✅ ZIP is clean (no git, venv, vendor, DB, uploads, or caches)"
fi

# Optional desktop shortcut install (opt-in)
if [ "$INSTALL_DESKTOP" -eq 1 ]; then
  if [ -f "$REPO_ROOT/scripts/install_desktop_shortcut.sh" ]; then
    echo
    echo "🖥️  Installing desktop shortcut (idempotent)..."
    echo "⚠️  IMPORTANT: Run this from ~/psi_repo (runtime repo), not ~/psi_codex."
    bash "$REPO_ROOT/scripts/install_desktop_shortcut.sh"
  else
    echo
    echo "⚠️  Desktop shortcut installer not found at scripts/install_desktop_shortcut.sh"
    echo "    (This is non-fatal; ZIP still built.)"
  fi
fi

echo
echo "🚀 Ready to upload or apply via overlay"
