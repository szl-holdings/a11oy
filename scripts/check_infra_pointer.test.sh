#!/usr/bin/env bash
# =============================================================================
# check_infra_pointer.test.sh — negative-fixture self-test for the infra/
# pointer guard.
#
# Builds throwaway infra/ trees and asserts that check_infra_pointer.py PASSES
# on a clean pointer-only tree and FAILS on each way an external repo copy can
# creep back in. This is what keeps the guard from being silently neutered.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_infra_pointer.py"

PASS=0
FAIL=0

run() { python3 "$GUARD" --infra "$1" >/dev/null 2>&1; }

expect_pass() {
  local name="$1" dir="$2"
  if run "$dir"; then
    echo "[PASS] $name (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $name (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
  fi
}

expect_fail() {
  local name="$1" dir="$2"
  if run "$dir"; then
    echo "[FAIL] $name (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $name (failed as expected)"; PASS=$((PASS + 1))
  fi
}

make_pointer() {
  mkdir -p "$1"
  echo "# Pointer — see https://github.com/szl-holdings/$(basename "$1")" > "$1/README.md"
}

make_big() {
  # $1 = dir, $2 = number of files
  mkdir -p "$1"
  for i in $(seq 1 "$2"); do echo "file $i" > "$1/f$i.txt"; done
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Fixture 1: clean pointer-only tree ------------------------------------
CLEAN="$TMP/clean/infra"
make_pointer "$CLEAN/uds-deployment"
make_pointer "$CLEAN/uds-mesh"
make_pointer "$CLEAN/uds-bundles"
make_pointer "$CLEAN/build-env"
# allowlisted a11oy-original dir may carry real files:
make_big "$CLEAN/receipts-samples" 6
expect_pass "clean pointer-only tree" "$CLEAN"

# --- Fixture 2: a pointer dir re-vendored into a full copy ------------------
REV="$TMP/revendored/infra"
make_pointer "$REV/uds-mesh"
make_pointer "$REV/uds-bundles"
make_big "$REV/uds-deployment" 30           # re-vendored! should fail
expect_fail "re-vendored pointer dir" "$REV"

# --- Fixture 3: brand-new full repo copy (multiple files) ------------------
NEW="$TMP/newcopy/infra"
make_pointer "$NEW/uds-deployment"
make_big "$NEW/some-other-repo" 12          # new vendored copy
expect_fail "new vendored copy (multiple files)" "$NEW"

# --- Fixture 4: pointer dir with README plus one extra file ----------------
EXTRA="$TMP/extra/infra"
make_pointer "$EXTRA/uds-mesh"
echo "extra" > "$EXTRA/uds-mesh/Chart.yaml"  # 2 files now → fail
expect_fail "pointer dir with an extra file" "$EXTRA"

# --- Fixture 5: single non-README file (count is 1 but not a pointer) ------
NONREADME="$TMP/nonreadme/infra"
mkdir -p "$NONREADME/sneaky"
echo "name: ci" > "$NONREADME/sneaky/main.tf"  # 1 file, but not README.md
expect_fail "single non-README file" "$NONREADME"

# --- Fixture 6: nested repo copy hidden under subdirs ----------------------
NEST="$TMP/nested/infra"
mkdir -p "$NEST/deep/.github/workflows"
echo "name: ci" > "$NEST/deep/.github/workflows/ci.yml"
echo "# deep" > "$NEST/deep/README.md"          # README + nested file → fail
expect_fail "nested repo copy under subdirs" "$NEST"

# --- Fixture 7: no infra dir at all ----------------------------------------
expect_pass "no infra dir" "$TMP/does-not-exist/infra"

# --- Fixture 8: empty placeholder dir --------------------------------------
EMPTY="$TMP/empty/infra"
mkdir -p "$EMPTY/placeholder"
expect_pass "empty placeholder dir" "$EMPTY"

echo
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
