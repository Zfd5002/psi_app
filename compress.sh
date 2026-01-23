#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------
# PSI code-only ZIP builder
# ----------------------------------------

# Repo root (assumes script lives in repo root)
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Default output location + name
VERSION="${1:-v1.1.9a}"
ZIP="$HOME/Downloads/psi_repo_update_${VERSION}_code_only.zip"

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
  -x ".git/*" \
  -x ".venv/*" \
  -x "uploads/*" \
  -x "psi/uploads/*" \
  -x "*.sqlite" -x "*.db" \
  -x "__pycache__/*" -x "**/__pycache__/*" \
  -x "*.pyc" -x "*.pyo" \
  -x ".pytest_cache/*" -x ".mypy_cache/*" -x ".ruff_cache/*" \
  -x "psi/web/templates/molecules/*.bak_*"

echo
echo "✅ ZIP created successfully"
ls -lh "$ZIP"

echo
echo "🔍 Verifying exclusions..."
if zipinfo -1 "$ZIP" | egrep -i '(\.git/|\.venv/|uploads/|\.sqlite$|\.db$|__pycache__/|\.pyc$)' >/dev/null; then
  echo "❌ ERROR: Forbidden files detected in ZIP"
  zipinfo -1 "$ZIP" | egrep -i '(\.git/|\.venv/|uploads/|\.sqlite$|\.db$|__pycache__/|\.pyc$)'
  exit 1
else
  echo "✅ ZIP is clean (no git, venv, DB, uploads, or caches)"
fi

echo
echo "🚀 Ready to upload or apply via overlay"
