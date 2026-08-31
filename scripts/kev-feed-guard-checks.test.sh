#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# kev-feed-guard-checks.test.sh — negative-fixture self-test for the KEV feed
# source guard. Proves each check (a) PASSES on the pristine source and (b) FAILS
# on a deliberately-broken copy that reverts the KEV feed URL to a cisa.gov host.
# Without this, a future refactor could neuter a check into a vacuous always-pass
# (green while guarding nothing) unnoticed.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
GUARD="$HERE/kev-feed-guard-checks.sh"
SRC="$ROOT/a11oy_vertical_feeds.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

[ -f "$SRC" ] || { echo "SELF-TEST FAIL: cannot find $SRC" >&2; exit 1; }

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

# 1) Pristine source passes every check.
for c in chk1 chk2; do expect_pass "$c" "$SRC" "pristine a11oy_vertical_feeds.py"; done

# 2) Revert the KEV feed URL to a www.cisa.gov host -> chk1 (mirror gone) and
#    chk2 (cisa.gov host present) must BOTH fail. This is the exact regression
#    the guard exists to catch.
sed -E 's#https://raw\.githubusercontent\.com/cisagov/kev-data/develop/known_exploited_vulnerabilities\.json#https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json#' \
  "$SRC" > "$TMP/reverted.py"
expect_fail chk1 "$TMP/reverted.py" "reverted-to-cisa.gov fixture (mirror missing)"
expect_fail chk2 "$TMP/reverted.py" "reverted-to-cisa.gov fixture (blocked host present)"

# 3) Comment-strip trap: the reverted source above, but with a header comment
#    that NAMES the mirror URL. The comment must NOT rescue chk1 — only a real
#    (non-comment) reference to the mirror counts.
awk '
  /^def[[:space:]]+feed_cisa_kev[[:space:]]*\(/ {
    print
    print "    # mirror: https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json"
    next
  }
  { print }
' "$TMP/reverted.py" > "$TMP/comment-only.py"
expect_fail chk1 "$TMP/comment-only.py" "comment-only-mirror fixture (no real reference)"

# 4) Comment-strip trap (chk2): the pristine (correct) source with a header
#    comment that NAMES a cisa.gov host. The comment must NOT trip chk2 — only a
#    real (non-comment) cisa.gov URL is a regression. (The real source already
#    carries such a comment, so the pristine pass in step 1 also exercises this,
#    but assert it explicitly for clarity.)
expect_pass chk2 "$SRC" "pristine source whose header comment names cisa.gov"

echo "All KEV feed source guard self-tests passed."
