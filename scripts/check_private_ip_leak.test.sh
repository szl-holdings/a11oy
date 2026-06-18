#!/usr/bin/env bash
# =============================================================================
# check_private_ip_leak.test.sh — self-test for the private-IP leak gate.
# =============================================================================
# Proves the gate (scripts/check_private_ip_leak.sh) actually CATCHES the leak
# class and that its allowlist is EXACT (not an always-pass). Runs the REAL gate
# against synthetic served trees in a temp dir — no network, pure bash.
#
# Exit 0 = all assertions pass; non-zero on the first failure.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="${SCRIPT_DIR}/check_private_ip_leak.sh"
PASS=0; FAIL=0

run_case() {  # name expected_exit  (sets SERVED_PATHS+ALLOWLIST_FILE in env)
  local name="$1" expected="$2"
  set +e
  ( cd "$WORK" && eval "$3" bash "$GATE" >/dev/null 2>&1 )
  local rc=$?
  set -e
  if [[ "$rc" == "$expected" ]]; then
    echo "  ok   — $name (exit $rc)"; PASS=$((PASS+1))
  else
    echo "  FAIL — $name (got $rc, want $expected)"; FAIL=$((FAIL+1))
  fi
}

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/web" "$WORK/static"

# --- clean tree: no leaks -> exit 0 -----------------------------------------
echo "<html>clean page http://localhost/ ok</html>" > "$WORK/web/clean.html"
run_case "clean tree passes" 0 "SERVED_PATHS='web static' ALLOWLIST_FILE=/dev/null"

# --- tailnet IP leak -> exit 1 ----------------------------------------------
echo 'endpoint: http://100.125.77.31:11434' > "$WORK/web/leak1.html"
run_case "tailnet 100.64/10 IP is caught" 1 "SERVED_PATHS='web static' ALLOWLIST_FILE=/dev/null"
rm -f "$WORK/web/leak1.html"

# --- box IP leak -> exit 1 --------------------------------------------------
echo 'box 167.233.50.75 here' > "$WORK/static/leak2.js"
run_case "box IP 167.233.50.75 is caught" 1 "SERVED_PATHS='web static' ALLOWLIST_FILE=/dev/null"

# --- box IP leak but allow-listed -> exit 0 ---------------------------------
echo 'static/leak2.js:167.233.50.75' > "$WORK/allow.txt"
run_case "box IP exempted by exact allowlist entry" 0 "SERVED_PATHS='web static' ALLOWLIST_FILE='$WORK/allow.txt'"

# --- allowlist must be EXACT: a DIFFERENT file with the same token still fails
echo 'box 167.233.50.75 elsewhere' > "$WORK/web/leak3.html"
run_case "allowlist does not leak across files" 1 "SERVED_PATHS='web static' ALLOWLIST_FILE='$WORK/allow.txt'"
rm -f "$WORK/web/leak3.html" "$WORK/static/leak2.js"

# --- internal port :11434 leak -> exit 1 ------------------------------------
echo 'base_url=http://10.0.0.5:11434/v1' > "$WORK/web/leak4.html"
run_case "internal port :11434 is caught" 1 "SERVED_PATHS='web static' ALLOWLIST_FILE=/dev/null"
rm -f "$WORK/web/leak4.html"

# --- :9471 internal port leak -> exit 1 -------------------------------------
echo 'upstream :9471 internal' > "$WORK/web/leak5.html"
run_case ":9471 internal port is caught" 1 "SERVED_PATHS='web static' ALLOWLIST_FILE=/dev/null"
rm -f "$WORK/web/leak5.html"

# --- public IP in 100.x but OUTSIDE 100.64/10 must NOT trip (e.g. 100.10.x) -
echo 'public 100.10.20.30 ok' > "$WORK/web/ok1.html"
run_case "100.x outside CGNAT range is NOT a false positive" 0 "SERVED_PATHS='web static' ALLOWLIST_FILE=/dev/null"
rm -f "$WORK/web/ok1.html"

echo ""
echo "private-ip-leak gate self-test: ${PASS} passed, ${FAIL} failed"
[[ "$FAIL" -eq 0 ]]
