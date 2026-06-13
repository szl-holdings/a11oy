#!/usr/bin/env bash
# =============================================================================
# check_putnam_drift.test.sh — negative-fixture self-test for the Putnam 2025
# drift guard (scripts/check_putnam_drift.py).
#
# Builds throwaway a11oy-shaped trees (szl_putnam.py loader + pages/console.html
# fallback) alongside an offline canonical Lutar/Putnam fixture, and asserts the
# guard PASSES on an honest tree and FAILS on every drift it is meant to catch:
# per-problem label drift, console-vs-loader divergence, count-phrase drift, a
# missing canonical problem file, named "X and Y are OPEN" prose drift, and SZL
# REAL-count drift. Runs fully offline via PUTNAM_DRIFT_FIXTURE (no network).
# This is what keeps the guard from silently being neutered.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_putnam_drift.py"

PASS=0
FAIL=0

run() {
  # $1 = a11oy root (its ./canon is the offline canonical fixture)
  PUTNAM_DRIFT_FIXTURE="$1/canon" python3 "$GUARD" --root "$1" >/dev/null 2>&1
}

expect_pass() {
  local name="$1" root="$2"
  if run "$root"; then
    echo "[PASS] $name (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $name (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
  fi
}

expect_fail() {
  local name="$1" root="$2"
  if run "$root"; then
    echo "[FAIL] $name (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $name (failed as expected)"; PASS=$((PASS + 1))
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------------------
# make_honest <root> — an internally consistent, honest a11oy tree.
# Canonical mini-set: A1 DEMO, A2 OPEN, A3 OPEN (0 REAL / 1 DEMO / 2 OPEN),
# plus one SZL original (REAL). Loader + console fallback both match it.
# ---------------------------------------------------------------------------
make_honest() {
  local r="$1"
  mkdir -p "$r/pages" "$r/canon/SZL"

  cat > "$r/szl_putnam.py" <<'PY'
"""szl_putnam test loader. Honest tally: 0 REAL / 1 DEMO / 2 OPEN.
A2 and A3 are OPEN. The SZL originals are 3 REAL ... well, 1 here."""
from typing import Any, Dict, List

_PUTNAM: List[Dict[str, str]] = [
    {"id": "A1", "file": "P_A1.lean", "title": "A1", "status": "DEMO", "note": "x"},
    {"id": "A2", "file": "P_A2.lean", "title": "A2", "status": "OPEN", "note": "x"},
    {"id": "A3", "file": "P_A3.lean", "title": "A3", "status": "OPEN", "note": "x"},
]
_SZL: List[Dict[str, Any]] = [
    {"id": "SZL-One", "file": "SZL/One.lean", "title": "One", "status": "REAL", "note": "x"},
]


def _putnam_block() -> Dict[str, Any]:
    real = sum(1 for p in _PUTNAM if p["status"] == "REAL")
    demo = sum(1 for p in _PUTNAM if p["status"] == "DEMO")
    open_ = sum(1 for p in _PUTNAM if p["status"] == "OPEN")
    return {"count": len(_PUTNAM), "real": real, "demo": demo, "open": open_}


def _szl_block() -> Dict[str, Any]:
    return {"count": len(_SZL), "real": sum(1 for s in _SZL if s["status"] == "REAL")}
PY

  cat > "$r/pages/console.html" <<'HTML'
<script>
// putnam-2025-tab-patch fallback
var FB_PROBS=[
 ['A1','P_A1.lean','DEMO','faithful statement; proof deferred'],
 ['A2','P_A2.lean','OPEN','corrected answer; main proof deferred'],
 ['A3','P_A3.lean','OPEN','corrected answer; main proof deferred']
];
var FB_SZL=[
 ['SZL-One','SZL/One.lean','REAL','kernel-clean original']
];
// headline: Putnam 2025 is 0 REAL / 1 DEMO / 2 OPEN. <b>A2</b> and <b>A3</b> are OPEN.
</script>
HTML

  printf '%s\n' '/-- Putnam A1. -/' '-- **Honest status: DEMO**' > "$r/canon/P_A1.lean"
  printf '%s\n' '/-- Putnam A2. -/' '-- **Honest status: OPEN**' > "$r/canon/P_A2.lean"
  printf '%s\n' '/-- Putnam A3. -/' '-- **Honest status: OPEN**' > "$r/canon/P_A3.lean"
  printf '%s\n' '/-- SZL original. All proofs are REAL (kernel-checked); no `sorry`. -/' \
    > "$r/canon/SZL/One.lean"
}

# --- Fixture A: honest tree -> PASS ----------------------------------------
A="$TMP/A"; make_honest "$A"
expect_pass "honest tree (loader == console == canonical 0/1/2, 1 SZL REAL)" "$A"

# --- Fixture B: loader per-problem label drift -> FAIL ---------------------
B="$TMP/B"; make_honest "$B"
sed -i 's/"id": "A3", "file": "P_A3.lean", "title": "A3", "status": "OPEN"/"id": "A3", "file": "P_A3.lean", "title": "A3", "status": "DEMO"/' "$B/szl_putnam.py"
expect_fail "loader per-problem label drift (A3 OPEN->DEMO vs canonical)" "$B"

# --- Fixture C: console fallback diverges from loader -> FAIL ---------------
C="$TMP/C"; make_honest "$C"
sed -i "s/\['A3','P_A3.lean','OPEN'/['A3','P_A3.lean','DEMO'/" "$C/pages/console.html"
expect_fail "console FB_PROBS diverges from loader (A3 OPEN->DEMO)" "$C"

# --- Fixture D: literal count-phrase drift in console -> FAIL ---------------
D="$TMP/D"; make_honest "$D"
sed -i 's#0 REAL / 1 DEMO / 2 OPEN#0 REAL / 3 DEMO / 0 OPEN#' "$D/pages/console.html"
expect_fail "console count phrase drift (claims 0/3/0 vs canonical 0/1/2)" "$D"

# --- Fixture E: canonical gains a problem the a11oy page never transcribed --
E="$TMP/E"; make_honest "$E"
printf '%s\n' '/-- Putnam B1. -/' '-- **Honest status: DEMO**' > "$E/canon/P_B1.lean"
expect_fail "missing canonical Putnam file (B1 added upstream, loader stale)" "$E"

# --- Fixture F: named "X and Y are OPEN" prose drift -> FAIL ----------------
F="$TMP/F"; make_honest "$F"
sed -i 's/<b>A2<\/b> and <b>A3<\/b> are OPEN/<b>A1<\/b> and <b>A2<\/b> are OPEN/' "$F/pages/console.html"
expect_fail "named-OPEN prose drift (says A1 and A2; canonical OPEN = A2,A3)" "$F"

# --- Fixture G: SZL REAL-count / label drift -> FAIL -----------------------
G="$TMP/G"; make_honest "$G"
sed -i 's/All proofs are REAL/All proofs are DEMO/' "$G/canon/SZL/One.lean"
expect_fail "SZL label/count drift (loader REAL vs canonical DEMO)" "$G"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
