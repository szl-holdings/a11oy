#!/usr/bin/env bash
# =============================================================================
# check_infra_vendoring.test.sh — negative-fixture self-test for the
# infra/ vendoring guard.
#
# Builds throwaway infra/ trees and asserts that check_infra_vendoring.py
# PASSES on a clean tree and FAILS on each way the drift can come back. This
# is what keeps the guard from silently being neutered.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_infra_vendoring.py"

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

# --- Fixture 1: clean tree -------------------------------------------------
CLEAN="$TMP/clean/infra"
make_pointer "$CLEAN/uds-deployment"
make_pointer "$CLEAN/uds-mesh"
make_pointer "$CLEAN/uds-bundles"
make_big "$CLEAN/fleet-overlay" 40          # allowlisted vendored copy — OK
mkdir -p "$CLEAN/new-pointer"; echo x > "$CLEAN/new-pointer/README.md"  # small new dir OK
expect_pass "clean tree" "$CLEAN"

# --- Fixture 2: a pointer dir re-vendored ----------------------------------
REV="$TMP/revendored/infra"
make_pointer "$REV/uds-mesh"
make_pointer "$REV/uds-bundles"
make_big "$REV/uds-deployment" 30           # re-vendored! should fail
expect_fail "re-vendored pointer dir" "$REV"

# --- Fixture 3: brand-new full repo copy (file count) ----------------------
NEW="$TMP/newcopy/infra"
make_pointer "$NEW/uds-deployment"
make_big "$NEW/some-other-repo" 25          # new vendored copy
expect_fail "new vendored copy (file count)" "$NEW"

# --- Fixture 4: new dir with repo-root marker, few files -------------------
MARK="$TMP/marker/infra"
make_pointer "$MARK/uds-deployment"
mkdir -p "$MARK/sneaky/.github/workflows"
echo "name: ci" > "$MARK/sneaky/.github/workflows/ci.yml"
echo "# sneaky" > "$MARK/sneaky/README.md"  # only 2 files but carries CI marker
expect_fail "new dir with repo-root marker" "$MARK"

# --- Fixture 5: no infra dir at all ----------------------------------------
expect_pass "no infra dir" "$TMP/does-not-exist/infra"

echo
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
