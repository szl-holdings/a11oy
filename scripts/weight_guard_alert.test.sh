#!/usr/bin/env bash
# =============================================================================
# weight_guard_alert.test.sh — offline self-test for the shared scheduled-run
# alert relay (scripts/weight_guard_alert.sh).
#
# The relay is a NOTIFICATION on an already-RED guard job, so its one hard
# contract is: it must NEVER turn into a second failure (never exit non-zero)
# and it must WARN — not silently swallow — when it cannot page. This proves:
#
#   - no MSG to relay                 -> exit 0 + a `::warning::` (nothing to page)
#   - no SLACK_WEBHOOK_URL set        -> exit 0 + a `::warning::` (cannot page)
#   - webhook set but UNREACHABLE     -> exit 0 + a non-200 `::warning::`
#                                        (the failing run remains the truth)
#
# All cases are network-free: the "unreachable" case points at a closed local
# port, so the suite runs the same in CI and locally.
# =============================================================================
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALERT="$HERE/weight_guard_alert.sh"

PASS=0
FAIL=0

# run_alert <msg> <webhook> -> captures combined output in $OUT, rc in $RC
run_alert() {
  OUT="$(MSG="$1" SLACK_WEBHOOK_URL="$2" bash "$ALERT" 2>&1)"
  RC=$?
}

check() {
  local desc="$1" want_rc="$2" want_substr="$3"
  if [ "$RC" -ne "$want_rc" ]; then
    echo "[FAIL] $desc (expected rc=$want_rc, got rc=$RC)"; FAIL=$((FAIL + 1))
    echo "$OUT" | sed 's/^/    /'
    return
  fi
  if ! printf '%s' "$OUT" | grep -qF "$want_substr"; then
    echo "[FAIL] $desc (output missing '$want_substr')"; FAIL=$((FAIL + 1))
    echo "$OUT" | sed 's/^/    /'
    return
  fi
  echo "[PASS] $desc (rc=$RC, warned as expected)"; PASS=$((PASS + 1))
}

# no MSG -> exit 0 + warning, nothing to page.
run_alert "" ""
check "no MSG to relay -> exit 0 + warning" 0 "no MSG to relay"

# MSG set but no webhook -> exit 0 + warning, cannot page.
run_alert "a11oy weight guard FAILED on its weekly re-verify." ""
check "no SLACK_WEBHOOK_URL -> exit 0 + warning" 0 "SLACK_WEBHOOK_URL is not set"

# MSG + an UNREACHABLE webhook (closed local port) -> exit 0 + non-200 warning.
# 127.0.0.1:9 (discard) is closed in CI; curl fails -> code 000 -> warning.
run_alert "a11oy weight guard FAILED on its weekly re-verify." "http://127.0.0.1:9/relay"
check "unreachable webhook -> exit 0 + non-200 warning" 0 "did not return 200"

echo ""
echo "self-test results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
echo "OK: the alert relay never masks the already-red job and warns when it cannot page."
