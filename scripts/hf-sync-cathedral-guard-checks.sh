#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# hf-sync-cathedral-guard-checks.sh — text-only invariants that keep hf-sync.yml's
# cathedral front-door coverage from silently regressing.
#
# Background
# ----------
# The redesigned a11oy.net hero is served from cathedral.html (repo ROOT) +
# static/a11oy_cathedral.js, which fall OUTSIDE the pages/console glob that
# hf-sync.yml mirrors to the public HuggingFace Space. Coverage for them lives in
# THREE places inside hf-sync.yml:
#   1. the on.push.paths trigger list   (so an edit fires the sync at all)
#   2. the add/update `patterns` glob    (so the file is mirrored to the Space)
#   3. the CATHEDRAL_FILES exact-match set consulted by is_front_door()
#      (so the delete-aware pass treats them as managed and never sweeps them off)
#
# A future edit to the workflow could quietly drop any of the three, re-opening
# the original drift gap (a GitHub-main edit silently failing to reach the Space)
# with NO warning. These pure-text checks (no network, no git, no cluster) catch
# that in seconds.
#
# Usage: hf-sync-cathedral-guard-checks.sh <chk1|chk2|chk3> <path-to-hf-sync.yml>
set -euo pipefail

CHK="${1:?usage: $0 <chk1|chk2|chk3> <hf-sync.yml>}"
WF="${2:?usage: $0 <chk1|chk2|chk3> <hf-sync.yml>}"

if [ ! -f "$WF" ]; then
  echo "FAIL[$CHK]: workflow file not found: $WF" >&2
  exit 1
fi

fail() { echo "FAIL[$CHK]: $1" >&2; exit 1; }
pass() { echo "PASS[$CHK]: $1"; exit 0; }

CATHEDRAL_HTML="cathedral.html"
CATHEDRAL_JS="static/a11oy_cathedral.js"

# Comment-stripped copy: drop whole-line YAML/Python comments (first non-space
# char is '#') so prose in the workflow's own header comment — which names the
# cathedral paths while DESCRIBING the coverage — can never satisfy a check.
NOCOMMENT="$(grep -vE '^[[:space:]]*#' "$WF")"

# Escape regex metacharacters in a literal path so '.' / '*' etc. are matched
# literally (the filenames contain '.' which is an ERE wildcard otherwise).
esc() { printf '%s' "$1" | sed -E 's/[][\\.^$*+?(){}|]/\\&/g'; }

# Extract the YAML on.push.paths sequence: from the `paths:` key down to the next
# sibling key (workflow_dispatch / permissions / jobs / on).
paths_block() {
  awk '
    /^[[:space:]]*paths:[[:space:]]*$/ { grab=1; next }
    grab && /^[[:space:]]*(workflow_dispatch|permissions|jobs|on):/ { grab=0 }
    grab { print }
  ' <<<"$NOCOMMENT"
}

# Extract a Python `<NAME> = [ ... ]` list assignment, from the opening `[`
# through the line that closes it with `]` (handles single- and multi-line).
list_block() { # <python-var-name>
  awk -v name="$1" '
    $0 ~ (name "[[:space:]]*=[[:space:]]*\\[") { grab=1 }
    grab { print }
    grab && /\]/ { exit }
  ' <<<"$NOCOMMENT"
}

# Extract the body of def is_front_door(...) up to its final `return d in (...)`.
is_front_door_body() {
  awk '
    /def[[:space:]]+is_front_door[[:space:]]*\(/ { grab=1 }
    grab { print }
    grab && /return[[:space:]]+d[[:space:]]+in/ { exit }
  ' <<<"$NOCOMMENT"
}

case "$CHK" in
  chk1)
    # COVERAGE POINT 1 — on.push.paths. Both cathedral files must appear as YAML
    # sequence items in the push-trigger path list, or an edit to either would
    # not even start hf-sync (silent drift, exactly the closed gap).
    block="$(paths_block)"
    [ -n "$block" ] || fail "could not locate the on.push.paths list"
    for f in "$CATHEDRAL_HTML" "$CATHEDRAL_JS"; do
      if ! grep -qE "^[[:space:]]*-[[:space:]]+[\"']?$(esc "$f")[\"']?[[:space:]]*\$" <<<"$block"; then
        fail "on.push.paths is missing '$f' — an edit to it would not trigger hf-sync"
      fi
    done
    pass "on.push.paths covers both cathedral files"
    ;;

  chk2)
    # COVERAGE POINT 2 — the add/update `patterns` glob. The cathedral files must
    # be reachable through it, either by spreading CATHEDRAL_FILES (*CATHEDRAL_FILES)
    # or by listing both literals; otherwise they are never mirrored to the Space.
    block="$(list_block patterns)"
    [ -n "$block" ] || fail "could not locate the 'patterns = [...]' add/update glob list"
    if grep -qE '\*[[:space:]]*CATHEDRAL_FILES\b' <<<"$block"; then
      pass "patterns glob spreads *CATHEDRAL_FILES (both cathedral files covered)"
    fi
    miss=0
    for f in "$CATHEDRAL_HTML" "$CATHEDRAL_JS"; do
      grep -qE "[\"']$(esc "$f")[\"']" <<<"$block" || miss=1
    done
    [ "$miss" -eq 0 ] && pass "patterns glob lists both cathedral files literally"
    fail "the add/update 'patterns' glob neither spreads *CATHEDRAL_FILES nor lists both cathedral files — they would not be mirrored to the Space"
    ;;

  chk3)
    # COVERAGE POINT 3 — the CATHEDRAL_FILES exact-match set AND its use in
    # is_front_door(). The set must list both files, and is_front_door() must
    # consult it, or the delete-aware pass would not treat the cathedral files as
    # managed and could sweep them off the Space.
    block="$(list_block CATHEDRAL_FILES)"
    [ -n "$block" ] || fail "could not locate the 'CATHEDRAL_FILES = [...]' set used by is_front_door()"
    for f in "$CATHEDRAL_HTML" "$CATHEDRAL_JS"; do
      grep -qE "[\"']$(esc "$f")[\"']" <<<"$block" || fail "CATHEDRAL_FILES is missing '$f' — the delete pass could sweep it off the Space"
    done
    body="$(is_front_door_body)"
    [ -n "$body" ] || fail "could not locate def is_front_door()"
    grep -qE '\bCATHEDRAL_FILES\b' <<<"$body" || fail "is_front_door() does not reference CATHEDRAL_FILES — the cathedral files would not be protected from the delete pass"
    pass "CATHEDRAL_FILES lists both cathedral files and is_front_door() consults it"
    ;;

  *)
    echo "unknown check: $CHK (expected chk1|chk2|chk3)" >&2
    exit 2
    ;;
esac
