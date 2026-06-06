#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
# ORCID: 0009-0001-0110-4173
#
# rebuild_all.sh — Idempotent rebuild of all anatomy figures
#
# Runs every build_anatomy_*.py script in the same directory.
# Idempotent: running twice produces the same output (scripts overwrite outputs).
#
# Usage: bash 05_anatomy/scripts/rebuild_all.sh
#        (or ./rebuild_all.sh from within the scripts/ directory)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "[rebuild_all] Rebuilding all anatomy figures"
echo "[rebuild_all] Directory: ${SCRIPT_DIR}"
echo ""

BUILT=0
FAILED=0

for f in build_anatomy_*.py; do
  if [ -f "${f}" ]; then
    echo "[rebuild_all] Running: python3 ${f}"
    if python3 "${f}"; then
      echo "[rebuild_all] OK: ${f}"
      BUILT=$((BUILT + 1))
    else
      echo "[rebuild_all] FAIL: ${f}" >&2
      FAILED=$((FAILED + 1))
    fi
  fi
done

echo ""
echo "[rebuild_all] Built: ${BUILT}  Failed: ${FAILED}"

if [ "${FAILED}" -gt 0 ]; then
  echo "[rebuild_all] FAIL — ${FAILED} script(s) returned non-zero" >&2
  exit 1
fi

echo "[rebuild_all] PASS — all anatomy figures rebuilt"
exit 0
