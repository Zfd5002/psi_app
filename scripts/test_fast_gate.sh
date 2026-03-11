#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ALLOWLIST_FILE="${REPO_ROOT}/tests/fast_gate_nodeids.txt"

if [[ ! -f "${ALLOWLIST_FILE}" ]]; then
  echo "fast gate allowlist missing: ${ALLOWLIST_FILE}" >&2
  exit 1
fi

mapfile -t NODEIDS < <(grep -Ev '^[[:space:]]*($|#)' "${ALLOWLIST_FILE}")
if [[ "${#NODEIDS[@]}" -eq 0 ]]; then
  echo "fast gate allowlist is empty: ${ALLOWLIST_FILE}" >&2
  exit 1
fi

cd "${REPO_ROOT}"
echo "PSI fast gate: running ${#NODEIDS[@]} curated tests from ${ALLOWLIST_FILE}"
pytest -q "${NODEIDS[@]}"
