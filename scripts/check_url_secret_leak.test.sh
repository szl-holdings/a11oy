#!/usr/bin/env bash
# =============================================================================
# check_url_secret_leak.test.sh — negative-fixture self-test for the
# "no finance API key in a URL / query string" guard.
#
# Writes throwaway Python fixtures and asserts that check_url_secret_leak.py
# PASSES on safe (header-based) code and FAILS on every shape of key-in-URL /
# key-in-query-string leak. This is what stops the guard from silently rotting
# into an always-pass. Pure Python + bash, no network.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$SCRIPT_DIR/check_url_secret_leak.py"
REAL_FILE="$SCRIPT_DIR/../a11oy_vertical_feeds.py"

PASS=0
FAIL=0

run() { python3 "$GUARD" --file "$1" >/dev/null 2>&1; }

expect_pass() {
  local name="$1" file="$2"
  if run "$file"; then
    echo "[PASS] $name (exit 0 as expected)"; PASS=$((PASS + 1))
  else
    echo "[FAIL] $name (expected exit 0, got non-zero)"; FAIL=$((FAIL + 1))
  fi
}

expect_fail() {
  local name="$1" file="$2"
  if run "$file"; then
    echo "[FAIL] $name (expected non-zero, got exit 0)"; FAIL=$((FAIL + 1))
  else
    echo "[PASS] $name (failed as expected)"; PASS=$((PASS + 1))
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Fixture: SAFE — key sent via Authorization header (the real pattern) ----
cat > "$TMP/safe_header.py" <<'PY'
import os
def feed_polygon(symbol):
    key = os.environ.get("POLYGON_API_KEY", "").strip()
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?adjusted=true"
    return _cached_fetch("poly_" + symbol, url, ttl=30,
                         headers={"Authorization": f"Bearer {key}"})
PY
expect_pass "safe: key in Authorization header only" "$TMP/safe_header.py"

# --- Fixture: SAFE — non-secret value (symbol) interpolated into the URL ------
cat > "$TMP/safe_symbol.py" <<'PY'
def feed(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d"
    return url
PY
expect_pass "safe: only a non-secret symbol in the URL" "$TMP/safe_symbol.py"

# --- Fixture: LEAK — key in an f-string URL ----------------------------------
cat > "$TMP/leak_fstring.py" <<'PY'
import os
def feed(symbol):
    key = os.environ.get("POLYGON_API_KEY", "")
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?apiKey={key}"
    return url
PY
expect_fail "leak: key in f-string URL" "$TMP/leak_fstring.py"

# --- Fixture: LEAK — key via string concatenation ----------------------------
cat > "$TMP/leak_concat.py" <<'PY'
import os
def feed(symbol):
    key = os.environ.get("POLYGON_API_KEY", "")
    base = "https://api.polygon.io/v2/aggs/ticker/" + symbol + "/prev"
    url = base + "?apiKey=" + key
    return url
PY
expect_fail "leak: key via + concatenation" "$TMP/leak_concat.py"

# --- Fixture: LEAK — key via %-format ----------------------------------------
cat > "$TMP/leak_percent.py" <<'PY'
import os
def feed(symbol):
    key = os.environ.get("POLYGON_API_KEY", "")
    url = "https://api.polygon.io/v2/aggs/ticker/%s/prev?apiKey=%s" % (symbol, key)
    return url
PY
expect_fail "leak: key via %-format" "$TMP/leak_percent.py"

# --- Fixture: LEAK — key via str.format --------------------------------------
cat > "$TMP/leak_format.py" <<'PY'
import os
def feed(symbol):
    key = os.environ.get("POLYGON_API_KEY", "")
    url = "https://api.polygon.io/v2/aggs/ticker/{}/prev?apiKey={}".format(symbol, key)
    return url
PY
expect_fail "leak: key via str.format" "$TMP/leak_format.py"

# --- Fixture: LEAK — inline os.environ read inside the URL -------------------
cat > "$TMP/leak_inline_env.py" <<'PY'
import os
def feed(symbol):
    url = f"https://api.polygon.io/prev?apiKey={os.environ['POLYGON_API_KEY']}"
    return url
PY
expect_fail "leak: inline os.environ read in URL" "$TMP/leak_inline_env.py"

# --- Fixture: LEAK — key passed as a params= query kwarg ----------------------
cat > "$TMP/leak_params.py" <<'PY'
import os, httpx
def feed(symbol):
    key = os.environ.get("POLYGON_API_KEY", "")
    with httpx.Client() as cl:
        return cl.get("https://api.polygon.io/v2/aggs", params={"apiKey": key})
PY
expect_fail "leak: key via params= query kwarg" "$TMP/leak_params.py"

# --- Fixture: LEAK — transitively-tainted variable in URL --------------------
cat > "$TMP/leak_transitive.py" <<'PY'
import os
def feed(symbol):
    raw = os.environ.get("POLYGON_API_KEY", "")
    token = raw.strip()
    suffix = "?apiKey=" + token
    url = "https://api.polygon.io/v2/aggs" + suffix
    return url
PY
expect_fail "leak: transitively-tainted var in URL" "$TMP/leak_transitive.py"

# --- Fixture: the REAL file must PASS ----------------------------------------
if [ -f "$REAL_FILE" ]; then
  expect_pass "real a11oy_vertical_feeds.py stays clean" "$REAL_FILE"
fi

echo
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
