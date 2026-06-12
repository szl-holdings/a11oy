#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# service-status-link-guard-checks.test.sh — negative-fixture self-test for the
# Service status link guard. Proves each check still PASSES on a good fixture and
# still FAILS on a deliberately-broken one, so a neutered check can't silently
# wave a regression through. Mirrors the repo's other guard self-tests
# (status-page-guard, hf-sync-cathedral-guard).
#
# No network, no git, no cluster. Exits non-zero on any regression.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CHECKS="$HERE/service-status-link-guard-checks.sh"

[ -f "$CHECKS" ] || { echo "SELFTEST FAIL: missing $CHECKS" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

good="$tmp/good.html"
cat > "$good" <<'EOF'
<header>
  <nav class="extlinks">
    <a class="flag" href="https://a11oy.net/" target="_blank">a11oy.net</a>
    <!-- service-status-link-patch -->
    <a class="flag" href="https://szl-holdings.github.io/a11oy/" target="_blank" rel="noopener noreferrer" title="a11oy live service-status board">&#9679; Service status</a>
  </nav>
</header>
EOF

# --- Positive: a good fixture must PASS both checks. ---
bash "$CHECKS" chk1 "$good" >/dev/null \
  || { echo "SELFTEST FAIL: chk1 should PASS on good fixture" >&2; exit 1; }
bash "$CHECKS" chk2 "$good" >/dev/null \
  || { echo "SELFTEST FAIL: chk2 should PASS on good fixture" >&2; exit 1; }

# --- Negative chk1: marker comment removed -> chk1 must FAIL. ---
no_marker="$tmp/no_marker.html"
grep -v 'service-status-link-patch' "$good" > "$no_marker"
if bash "$CHECKS" chk1 "$no_marker" >/dev/null 2>&1; then
  echo "SELFTEST FAIL: chk1 passed despite the missing marker" >&2; exit 1
fi

# --- Negative chk2: the status-board anchor removed -> chk2 must FAIL. ---
no_link="$tmp/no_link.html"
grep -v 'szl-holdings.github.io/a11oy' "$good" > "$no_link"
if bash "$CHECKS" chk2 "$no_link" >/dev/null 2>&1; then
  echo "SELFTEST FAIL: chk2 passed despite the missing status-board link" >&2; exit 1
fi

# --- Negative chk2: href changed to a different URL -> chk2 must FAIL. ---
wrong_href="$tmp/wrong_href.html"
sed 's#https://szl-holdings\.github\.io/a11oy/#https://example.com/#' "$good" > "$wrong_href"
if bash "$CHECKS" chk2 "$wrong_href" >/dev/null 2>&1; then
  echo "SELFTEST FAIL: chk2 passed despite the href pointing elsewhere" >&2; exit 1
fi

echo "SELFTEST OK: checks pass on the good fixture and fail on every broken fixture"
