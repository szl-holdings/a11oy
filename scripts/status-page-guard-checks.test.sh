#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# status-page-guard-checks.test.sh — negative-fixture self-test for the status
# page guard. Proves each check (a) PASSES on the pristine status-page.yml and
# (b) FAILS on a deliberately-broken copy that reintroduces the regression that
# check defends against. Without this, a future refactor could neuter a check
# into a vacuous always-pass (green while guarding nothing) unnoticed.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
GUARD="$HERE/status-page-guard-checks.sh"
WF="$ROOT/.github/workflows/status-page.yml"
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
for c in chk1 chk2 chk3; do expect_pass "$c" "$WF" "pristine status-page.yml"; done

# 2) Drop the force flag -> chk1 must fail.
sed -E 's/git push -f origin status-publish:status/git push origin status-publish:status/' \
  "$WF" > "$TMP/no-force.yml"
expect_fail chk1 "$TMP/no-force.yml" "no-force-flag fixture"

# 3) Push to the default branch -> chk2 must fail.
sed -E 's/git push -f origin status-publish:status/git push origin main/' \
  "$WF" > "$TMP/push-main.yml"
expect_fail chk2 "$TMP/push-main.yml" "push-to-main fixture"

# 4) Swallow the push error + drop set -e -> chk3 must fail.
sed -E 's/git push -f origin status-publish:status/git push -f origin status-publish:status || true/; s/set -euo pipefail/set +e/' \
  "$WF" > "$TMP/swallow.yml"
expect_fail chk3 "$TMP/swallow.yml" "error-swallow fixture"

echo "All status-page guard self-tests passed."
