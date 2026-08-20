#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# kev-feed-guard-checks.sh — text-only invariants that keep the server-side CISA
# KEV feed pointed at a reachable source so it cannot silently go DEGRADED again.
#
# Background
# ----------
# www.cisa.gov returns 403 Forbidden to Hetzner/datacenter egress IPs (Akamai
# bot/geo block), so the box-hosted server-side feed_cisa_kev() (in
# a11oy_vertical_feeds.py) reported DEGRADED (freshness.status:"unavailable")
# whenever its URL pointed at a cisa.gov host. The fix (re: the KEV feed repoint)
# swapped the source to the cisagov GitHub mirror
#   https://raw.githubusercontent.com/cisagov/kev-data/develop/known_exploited_vulnerabilities.json
# which carries the identical authoritative catalog and IS reachable server-side.
#
# A future edit could quietly revert the URL back to a cisa.gov host, re-opening
# the original gap with NO test catching it. These pure-text checks (no network,
# no git, no cluster) FAIL in seconds if that happens:
#   chk1  feed_cisa_kev() no longer references the reachable cisagov GitHub mirror
#   chk2  feed_cisa_kev() references a (datacenter-blocked) cisa.gov host URL
#
# Mirrors the org guard pattern (hf-sync-cathedral-guard, status-page-guard): a
# self-test job proves each check still FAILS on a broken fixture before the guard
# job trusts it against the real source.
#
# Usage: kev-feed-guard-checks.sh <chk1|chk2> <path-to-a11oy_vertical_feeds.py>
set -euo pipefail

CHK="${1:?usage: $0 <chk1|chk2> <a11oy_vertical_feeds.py>}"
SRC="${2:?usage: $0 <chk1|chk2> <a11oy_vertical_feeds.py>}"

if [ ! -f "$SRC" ]; then
  echo "FAIL[$CHK]: source file not found: $SRC" >&2
  exit 1
fi

fail() { echo "FAIL[$CHK]: $1" >&2; exit 1; }
pass() { echo "PASS[$CHK]: $1"; exit 0; }

# Extract the body of `def feed_cisa_kev(...)` from its def line down to (but not
# including) the next top-level `def ` or the LIVE-FEED section divider. We scope
# the checks to this function so an unrelated feed elsewhere in the file (or a
# benign URL in another parser) can never satisfy or trip them.
fn_body() {
  awk '
    /^def[[:space:]]+feed_cisa_kev[[:space:]]*\(/ { grab=1; print; next }
    grab && /^def[[:space:]]/ { exit }
    grab { print }
  ' "$SRC"
}

# Comment-stripped copy: drop whole-line Python comments (first non-space char is
# "#") so the function's own header comment — which NAMES cisa.gov while
# explaining WHY it is avoided — can never satisfy (chk1) or trip (chk2) a check.
BODY="$(fn_body)"
[ -n "$BODY" ] || fail "could not locate def feed_cisa_kev() in $SRC"
NOCOMMENT="$(grep -vE '^[[:space:]]*#' <<<"$BODY")"

# The reachable cisagov GitHub mirror (note: "cisagov", no dot — distinct from
# the blocked "cisa.gov" host).
MIRROR='raw\.githubusercontent\.com/cisagov/kev-data'

case "$CHK" in
  chk1)
    # feed_cisa_kev() must still source from the reachable cisagov GitHub mirror.
    if grep -qE "$MIRROR" <<<"$NOCOMMENT"; then
      pass "feed_cisa_kev() sources from the reachable cisagov GitHub mirror"
    fi
    fail "feed_cisa_kev() no longer references the cisagov GitHub mirror (raw.githubusercontent.com/cisagov/kev-data) — the KEV feed may silently DEGRADE on the box"
    ;;

  chk2)
    # feed_cisa_kev() must NOT reference a cisa.gov host URL (it 403s the box).
    # Match a URL whose host contains the literal "cisa.gov"; the cisagov mirror
    # ("cisagov", no dot) is intentionally NOT matched.
    if grep -qE 'https?://[^"'"'"' )]*cisa\.gov' <<<"$NOCOMMENT"; then
      fail "feed_cisa_kev() references a cisa.gov host URL — that host 403s datacenter/box egress and the KEV feed will report DEGRADED; use the cisagov GitHub mirror instead"
    fi
    pass "feed_cisa_kev() references no datacenter-blocked cisa.gov host URL"
    ;;

  *)
    echo "unknown check: $CHK (expected chk1|chk2)" >&2
    exit 2
    ;;
esac
