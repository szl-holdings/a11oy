#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# hf-sync-cathedral-guard-checks.test.sh — negative-fixture self-test for the
# hf-sync cathedral coverage guard. Proves each check (a) PASSES on the pristine
# hf-sync.yml and (b) FAILS on a deliberately-broken copy that drops the coverage
# that check defends against. Without this, a future refactor could neuter a
# check into a vacuous always-pass (green while guarding nothing) unnoticed.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
GUARD="$HERE/hf-sync-cathedral-guard-checks.sh"
WF="$ROOT/.github/workflows/hf-sync.yml"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

[ -f "$WF" ] || { echo "SELF-TEST FAIL: cannot find $WF" >&2; exit 1; }

expect_pass() { # <chk> <file> <label>
  if bash "$GUARD" "$1" "$2" >/dev/null 2>&1; then
    echo "ok: $1 PASSES on $3"
  else
    echo "SELF-TEST FAIL: $1 should PASS on $3" >&2; exit 1
  fi
}
expect_fail() { # <chk> <file> <label>
  if bash "$GUARD" "$1" "$2" >/dev/null 2>&1; then
    echo "SELF-TEST FAIL: $1 should FAIL on $3 (guard passed vacuously)" >&2; exit 1
  else
    echo "ok: $1 FAILS on $3"
  fi
}

# 1) Pristine workflow passes every check.
for c in chk1 chk2 chk3; do expect_pass "$c" "$WF" "pristine hf-sync.yml"; done

# 2) Drop static/a11oy_cathedral.js from on.push.paths -> chk1 must fail.
#    (Removes only the YAML sequence item; the Python uses a different syntax.)
sed -E '/^[[:space:]]*-[[:space:]]+"static\/a11oy_cathedral\.js"[[:space:]]*$/d' \
  "$WF" > "$TMP/no-pushpath.yml"
expect_fail chk1 "$TMP/no-pushpath.yml" "missing-on.push.paths fixture"

# 3) Drop the *CATHEDRAL_FILES spread from the patterns glob -> chk2 must fail.
sed -E 's/\*CATHEDRAL_FILES//' "$WF" > "$TMP/no-glob.yml"
expect_fail chk2 "$TMP/no-glob.yml" "missing-patterns-glob fixture"

# 4) Drop a file from the CATHEDRAL_FILES set -> chk3 must fail.
sed -E 's/, "static\/a11oy_cathedral\.js"\]/]/' "$WF" > "$TMP/short-set.yml"
expect_fail chk3 "$TMP/short-set.yml" "shortened-CATHEDRAL_FILES fixture"

# 5) Make is_front_door() stop consulting CATHEDRAL_FILES -> chk3 must fail
#    (delete pass would no longer treat the cathedral files as managed).
sed -E 's/if p in CATHEDRAL_FILES:/if False:/' "$WF" > "$TMP/deref.yml"
expect_fail chk3 "$TMP/deref.yml" "is_front_door-deref fixture"

# 6) A header comment that merely NAMES the paths must NOT satisfy the checks
#    (comment-stripping trap). Strip the real coverage but keep the prose.
sed -E '/^[[:space:]]*-[[:space:]]+"cathedral\.html"[[:space:]]*$/d; /^[[:space:]]*-[[:space:]]+"static\/a11oy_cathedral\.js"[[:space:]]*$/d' \
  "$WF" > "$TMP/comment-only.yml"
expect_fail chk1 "$TMP/comment-only.yml" "comment-only (no real path) fixture"

echo "All hf-sync cathedral guard self-tests passed."
