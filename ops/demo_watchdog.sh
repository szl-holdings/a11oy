#!/usr/bin/env bash
# ops/demo_watchdog.sh - lightweight liveness loop for the warhacker demo.
# Every INTERVAL seconds it checks the surfaces that MUST be up for the demo
# (root page + energy operator running & not stubbed & >=1 lung) and prints one
# timestamped GREEN/RED line. On a GREEN<->RED transition it can POST to an
# optional ntfy topic (ASCII title only). Honest: RED is shown the instant a
# real check fails; it never prints GREEN on a failed probe.
# Usage: ops/demo_watchdog.sh [BASE]
#   env: WATCHDOG_INTERVAL (default 30), WATCHDOG_NTFY_URL (optional)
set -uo pipefail
BASE="${1:-${A11OY_BASE:-https://a11oy.net}}"
INTERVAL="${WATCHDOG_INTERVAL:-30}"
NTFY="${WATCHDOG_NTFY_URL:-}"
UA="demo-watchdog/1.0"
last=""
op_ok(){ curl -sS -A "$UA" --max-time 12 "$BASE/api/a11oy/v1/energy/operator/status" 2>/dev/null | python3 -c "import sys,json
try: d=json.load(sys.stdin)
except Exception: print('0'); sys.exit()
print('1' if (d.get('running') and d.get('stub_mode') is False and len(d.get('nodes_computing') or [])>0) else '0')" 2>/dev/null || echo 0; }
echo "demo_watchdog: $BASE every ${INTERVAL}s (Ctrl-C to stop)"
while :; do
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  root="$(curl -sS -A "$UA" --max-time 12 -o /dev/null -w '%{http_code}' "$BASE/" 2>/dev/null || echo 000)"
  op="$(op_ok)"
  if [ "$root" = 200 ] && [ "$op" = 1 ]; then state=GREEN; else state=RED; fi
  printf '[%s] %-5s root=%s operator_lung=%s\n' "$ts" "$state" "$root" "$op"
  if [ -n "$NTFY" ] && [ "$state" != "$last" ] && [ -n "$last" ]; then
    curl -sS -H "Title: warhacker demo $state" -d "root=$root operator=$op at $ts" "$NTFY" >/dev/null 2>&1 || true
  fi
  last="$state"
  sleep "$INTERVAL"
done
