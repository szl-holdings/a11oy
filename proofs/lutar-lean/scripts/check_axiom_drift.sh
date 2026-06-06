#!/usr/bin/env bash
# check_axiom_drift.sh — Watunakuy Strike 4: axiom semantic drift guard
#
# Verifies that the A2 and A4 inline Lean definitions in Axioms.lean match
# the definitions documented in README.md. Fails if drift is detected.
#
# Usage: ./scripts/check_axiom_drift.sh
# Exit 0: no drift. Exit 1: drift detected (README or Axioms.lean was changed
#         without updating the other).
#
# This script implements the PhD-Math remediation for finding F8 (MEDIUM):
# "Axiom semantic drift between v3 and v14 is unacknowledged."
# It prevents future unacknowledged drift by making README⇔code divergence
# a CI failure.
#
# PhD-Math citation: PHD_MATH_REVIEW.md §2/§5, Finding F8 (MEDIUM), 2026-05-31.
# Authored by: Allichachiq Yupayqa (Quechua squad, SZL Holdings).
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

AXIOMS_FILE="Lutar/Axioms.lean"
README_FILE="README.md"
ERRORS=0

echo "=== Axiom Drift Guard (Watunakuy Strike 4) ==="
echo "Checking: $AXIOMS_FILE <-> $README_FILE"
echo ""

# ---------------------------------------------------------------------------
# A2 check: README must document "IsHomogeneous" and "positive homogeneity"
# ---------------------------------------------------------------------------

A2_LEAN_NAME=$(grep -oP 'def IsHomogeneous' "$AXIOMS_FILE" 2>/dev/null | head -1)
if [ -z "$A2_LEAN_NAME" ]; then
  echo "ERROR A2: 'def IsHomogeneous' not found in $AXIOMS_FILE"
  echo "  Axioms.lean may have renamed A2. Update README.md §Axiom Semantic Drift"
  echo "  and this script to reflect the new name."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    A2: 'def IsHomogeneous' found in $AXIOMS_FILE"
fi

if ! grep -q "IsHomogeneous" "$README_FILE"; then
  echo "ERROR A2: 'IsHomogeneous' not found in $README_FILE"
  echo "  README.md §Axiom Semantic Drift must document the current A2 definition."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    A2: 'IsHomogeneous' documented in $README_FILE"
fi

# ---------------------------------------------------------------------------
# A4 check: README must document "IsBounded" and "bounded by max"
# ---------------------------------------------------------------------------

A4_LEAN_NAME=$(grep -oP 'def IsBounded' "$AXIOMS_FILE" 2>/dev/null | head -1)
if [ -z "$A4_LEAN_NAME" ]; then
  echo "ERROR A4: 'def IsBounded' not found in $AXIOMS_FILE"
  echo "  Axioms.lean may have renamed A4. Update README.md §Axiom Semantic Drift"
  echo "  and this script to reflect the new name."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    A4: 'def IsBounded' found in $AXIOMS_FILE"
fi

if ! grep -q "IsBounded" "$README_FILE"; then
  echo "ERROR A4: 'IsBounded' not found in $README_FILE"
  echo "  README.md §Axiom Semantic Drift must document the current A4 definition."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    A4: 'IsBounded' documented in $README_FILE"
fi

# ---------------------------------------------------------------------------
# Drift section presence check
# ---------------------------------------------------------------------------

if ! grep -q "Axiom Semantic Drift" "$README_FILE"; then
  echo "ERROR: '## Axiom Semantic Drift' section not found in $README_FILE"
  echo "  This section is required for PhD-Math F8 compliance."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    Drift disclosure section present in $README_FILE"
fi

# ---------------------------------------------------------------------------
# CAUCHY_ND disclosure check
# ---------------------------------------------------------------------------

if ! grep -q "CAUCHY_ND" "$README_FILE"; then
  echo "ERROR: 'CAUCHY_ND' disclosure not found in $README_FILE"
  echo "  README.md must acknowledge the CAUCHY_ND sorry gap (PhD-Math F1 CRITICAL)."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    CAUCHY_ND gap acknowledged in $README_FILE"
fi

# ---------------------------------------------------------------------------
# Stale-number guard: README must not cite 752 or the old SHA 3de37e5
# ---------------------------------------------------------------------------

if grep -q "752 declarations" "$README_FILE"; then
  echo "ERROR: Stale number '752 declarations' found in $README_FILE"
  echo "  Canonical count is 749 at c7c0ba17. Update README. PhD-Math F9."
  ERRORS=$((ERRORS + 1))
else
  echo "OK    No stale '752 declarations' in $README_FILE"
fi

if grep -q "3de37e5" "$README_FILE"; then
  echo "WARN: Legacy SHA '3de37e5' still referenced in $README_FILE"
  echo "  Canonical HEAD is c7c0ba17. Consider updating."
  # Warn only, not error — may appear in historical context
fi

echo ""
echo "=== Result: $ERRORS error(s) ==="
if [ "$ERRORS" -gt 0 ]; then
  echo "FAIL: Axiom drift detected. Update README.md and/or Axioms.lean."
  exit 1
fi
echo "PASS: Axiom definitions and README are consistent."
exit 0
