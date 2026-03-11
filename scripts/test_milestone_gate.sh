#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGETS_FILE="${REPO_ROOT}/tests/milestone_gate_targets.txt"

if [[ ! -f "${TARGETS_FILE}" ]]; then
  echo "milestone gate target list missing: ${TARGETS_FILE}" >&2
  exit 1
fi

mapfile -t TARGETS < <(grep -Ev '^[[:space:]]*($|#)' "${TARGETS_FILE}")
if [[ "${#TARGETS[@]}" -eq 0 ]]; then
  echo "milestone gate target list is empty: ${TARGETS_FILE}" >&2
  exit 1
fi

cd "${REPO_ROOT}"
echo "PSI milestone gate: fast gate + ${#TARGETS[@]} curated files"
bash "${REPO_ROOT}/scripts/test_fast_gate.sh"
pytest -q "${TARGETS[@]}"
