#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# service-status-link-guard-checks.sh — text-only invariants that keep the
# in-app "Service status" link from silently disappearing out of the a11oy
# console's top-bar "Project links" nav.
#
# Background
# ----------
# pages/console.html is a large (~1.1MB) served file that is concurrently edited
# by sibling agents and periodically rewritten by CI auto-commits. The console's
# top-bar `<nav class="extlinks">` block carries a "Service status" link that
# points at the public live status board (https://szl-holdings.github.io/a11oy/),
# tagged in the source with the comment marker `service-status-link-patch`. A
# future edit or auto-commit could drop the link without anyone noticing, leaving
# users with no in-app path to the status board.
#
# These pure-text checks (no network, no git, no cluster) catch that in seconds:
#   chk1  the `service-status-link-patch` marker comment is present
#   chk2  an <a> anchor whose href is exactly the live status-board URL exists
#
# Usage: service-status-link-guard-checks.sh <chk1|chk2> <path-to-console.html>
set -euo pipefail

CHK="${1:?usage: $0 <chk1|chk2> <console.html>}"
HTML="${2:?usage: $0 <chk1|chk2> <console.html>}"

if [ ! -f "$HTML" ]; then
  echo "FAIL[$CHK]: file not found: $HTML" >&2
  exit 1
fi

fail() { echo "FAIL[$CHK]: $1" >&2; exit 1; }
pass() { echo "PASS[$CHK]: $1"; exit 0; }

MARKER='service-status-link-patch'
HREF='https://szl-holdings.github.io/a11oy/'

case "$CHK" in
  chk1)
    # The marker comment makes the Service status link block identifiable so it
    # is never refactored away by accident.
    if grep -Fq -- "$MARKER" "$HTML"; then
      pass "marker '$MARKER' present"
    fi
    fail "marker '$MARKER' missing — the Service status link block is no longer identifiable"
    ;;

  chk2)
    # An <a> anchor whose href is EXACTLY the live service-status board URL must
    # exist. Match the href attribute on an anchor tag; '.' is escaped so the
    # pattern is a literal URL match, not a wildcard.
    if grep -nE '<a[^>]*href="https://szl-holdings\.github\.io/a11oy/"' "$HTML" | grep -q .; then
      pass "anchor with href '$HREF' present"
    fi
    fail "no <a> with href '$HREF' found — the Service status link was dropped"
    ;;

  *)
    echo "unknown check: $CHK (expected chk1|chk2)" >&2
    exit 2
    ;;
esac
