#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# status-page-guard-checks.sh — text-only invariants that keep status-page.yml's
# publish step from silently regressing to the old, broken behavior.
#
# Background
# ----------
# status-page.yml was silently broken for a long time: it committed the generated
# STATUS.md to the checked-out *default* branch and `git push`ed it. Branch
# protection rejects a push to the default branch, but the failure surfaced only
# as a non-fatal log line, so the "public" status board never updated and only
# ever lived inside the workflow run logs. The fix (2026-06-09) force-pushes a
# single orphan commit carrying STATUS.md + a Pages-ready index.html to the
# dedicated, UNPROTECTED `status` branch each run.
#
# A future edit could quietly revert any piece of that — push to main again, drop
# the force-push, or wrap the push in `|| true` so a rejection is swallowed —
# re-opening the exact "board only lives in run logs" hole. These pure-text
# checks (no network, no git, no cluster) catch that in seconds.
#
# Usage: status-page-guard-checks.sh <chk1|chk2|chk3> <path-to-status-page.yml>
set -euo pipefail

CHK="${1:?usage: $0 <chk1|chk2|chk3> <status-page.yml>}"
WF="${2:?usage: $0 <chk1|chk2|chk3> <status-page.yml>}"

if [ ! -f "$WF" ]; then
  echo "FAIL[$CHK]: workflow file not found: $WF" >&2
  exit 1
fi

fail() { echo "FAIL[$CHK]: $1" >&2; exit 1; }
pass() { echo "PASS[$CHK]: $1"; exit 0; }

# Line-numbered grep that ignores YAML comment lines (first non-space char is
# '#'), so prose in the workflow's header comment never trips a check.
cgrep() { grep -nE "$1" "$WF" | grep -vE '^[0-9]+:[[:space:]]*#' || true; }

case "$CHK" in
  chk1)
    # The publish step MUST force-push the generated status surface to the
    # dedicated `status` branch. Accept -f / --force / --force-with-lease and a
    # `<src>:status` refspec.
    if cgrep '\bgit[[:space:]]+push[[:space:]]+(-f|--force|--force-with-lease)\b[^|&]*:[[:space:]]*status\b' | grep -q .; then
      pass "force-push to the 'status' branch is present"
    fi
    fail "no 'git push --force ...:status' found — the status board would not be published to the public 'status' branch"
    ;;

  chk2)
    # No git push may target the default branch, and every push must explicitly
    # target the 'status' branch. Catches a regression to 'git push origin main',
    # 'HEAD:main', or a bare 'git push' (ambiguous — could push the checked-out
    # default branch, which is exactly the original bug).
    lines="$(cgrep '\bgit[[:space:]]+push\b')"
    [ -n "$lines" ] || fail "no 'git push' at all — STATUS.md would never reach a public branch"
    while IFS= read -r line; do
      [ -z "$line" ] && continue
      cmd="${line#*:}"   # strip the "NN:" line-number prefix
      if echo "$cmd" | grep -qE ':[[:space:]]*main\b|[[:space:]]main\b|HEAD:main'; then
        fail "a 'git push' targets the default branch (main): $cmd"
      fi
      if ! echo "$cmd" | grep -qE ':[[:space:]]*status\b'; then
        fail "a 'git push' does not target the 'status' branch (ambiguous/unsafe): $cmd"
      fi
    done <<EOF
$lines
EOF
    pass "every 'git push' targets the 'status' branch; none target main"
    ;;

  chk3)
    # A rejected publish must FAIL the job, not be swallowed as a non-fatal log
    # line (the original bug). Forbid error-swallowing on the status push and
    # require the publishing step to run under 'set -e'.
    if cgrep '\bgit[[:space:]]+push\b[^#]*:[[:space:]]*status\b' | grep -qE '\|\|[[:space:]]*(true|:|echo)'; then
      fail "the status-branch push swallows its error (|| true / || echo / || :) — a failed publish would go unnoticed"
    fi
    if cgrep 'continue-on-error:[[:space:]]*true' | grep -q .; then
      fail "continue-on-error: true is set — a failed publish could be masked"
    fi
    pushln="$(cgrep '\bgit[[:space:]]+push\b[^#]*:[[:space:]]*status\b' | head -1 | cut -d: -f1)"
    [ -n "$pushln" ] || fail "no status push found to evaluate"
    # Anchor the lookback to the START of the step that contains the push (the
    # nearest preceding `- name:` step header), not a brittle fixed line count.
    # The publish step body grows over time (e.g. an inline Markdown renderer was
    # added), so a hardcoded N-line window would silently drift off the step's
    # `set -e` and fail on a perfectly-correct workflow. Scoping to the step is
    # STRICTER: the `set -e` must live in the SAME step as the push, not just
    # somewhere within N lines of it.
    start="$(sed -n "1,${pushln}p" "$WF" | grep -nE '^[[:space:]]*-[[:space:]]+name:' | tail -1 | cut -d: -f1)"
    [ -n "$start" ] || start=1
    if ! sed -n "${start},${pushln}p" "$WF" | grep -qE '\bset[[:space:]]+-[a-z]*e'; then
      fail "the publish step does not 'set -e' above the status push — a rejected push would not fail the job"
    fi
    pass "publish failures are fatal (set -e present, status push error not swallowed)"
    ;;

  *)
    echo "unknown check: $CHK (expected chk1|chk2|chk3)" >&2
    exit 2
    ;;
esac
