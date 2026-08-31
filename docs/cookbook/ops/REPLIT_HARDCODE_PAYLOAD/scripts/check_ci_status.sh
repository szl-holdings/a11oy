#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# check_ci_status.sh — For every open PR, report latest CI rollup.
# Reads data/all_open_prs.json. Writes out/ci_status.md and out/ci_status.json.

. "$(dirname "$0")/_lib.sh"
require_jq

PRS="$DATA_DIR/all_open_prs.json"
[ -f "$PRS" ] || { err "Run pull_pr_state.sh first."; exit 1; }

OUT_MD="$OUT_DIR/ci_status.md"
OUT_JSON="$OUT_DIR/ci_status.json"

hdr "Computing CI rollup for every open PR"

{
  echo "# CI Status — Open PRs"
  echo
  echo "Generated: $(date -u +%FT%TZ)"
  echo
  echo "| Repo | PR | Title | Draft | Mergeable | CI |"
  echo "|------|----|-------|-------|-----------|-----|"
} > "$OUT_MD"

jq -c '.[]' "$PRS" | while IFS= read -r pr; do
  repo=$(echo "$pr" | jq -r '.repo')
  num=$(echo "$pr"  | jq -r '.number')
  title=$(echo "$pr" | jq -r '.title' | sed 's/|/\\|/g')
  draft=$(echo "$pr" | jq -r '.isDraft')
  mergeable=$(echo "$pr" | jq -r '.mergeStateStatus // "?"')
  # statusCheckRollup is array of {state, conclusion, name}; pick worst.
  ci=$(echo "$pr" | jq -r '
    if (.statusCheckRollup // [] | length) == 0 then "NONE"
    else
      ( .statusCheckRollup
        | map(.conclusion // .status // "PENDING")
        | if any(.=="FAILURE") then "FAIL"
          elif any(.=="CANCELLED") then "CANCELLED"
          elif any(.=="ACTION_REQUIRED") then "ACTION_REQ"
          elif any(.=="TIMED_OUT") then "TIMEOUT"
          elif any(.=="PENDING" or .=="IN_PROGRESS" or .=="QUEUED") then "PENDING"
          elif all(.=="SUCCESS" or .=="NEUTRAL" or .=="SKIPPED") then "PASS"
          else "MIXED" end
      )
    end')
  printf '| %s | #%s | %s | %s | %s | %s |\n' "$repo" "$num" "$title" "$draft" "$mergeable" "$ci" >> "$OUT_MD"
done

jq '[.[] | {repo, number, title, isDraft, mergeStateStatus, ci_rollup:
  (if (.statusCheckRollup // [] | length) == 0 then "NONE"
   else
     ( .statusCheckRollup
       | map(.conclusion // .status // "PENDING")
       | if any(.=="FAILURE") then "FAIL"
         elif any(.=="PENDING" or .=="IN_PROGRESS" or .=="QUEUED") then "PENDING"
         elif all(.=="SUCCESS" or .=="NEUTRAL" or .=="SKIPPED") then "PASS"
         else "MIXED" end
     )
   end)
}]' "$PRS" > "$OUT_JSON"

fails=$(jq '[.[] | select(.ci_rollup=="FAIL")] | length' "$OUT_JSON")
pending=$(jq '[.[] | select(.ci_rollup=="PENDING")] | length' "$OUT_JSON")
pass=$(jq '[.[] | select(.ci_rollup=="PASS")] | length' "$OUT_JSON")
total=$(jq 'length' "$OUT_JSON")

ok "Total open: $total | PASS: $pass | PENDING: $pending | FAIL: $fails"
log "Report: $OUT_MD"

# Exit non-zero only if CI is FAILING on PRs we care about (not draft).
nonblocker_fails=$(jq '[.[] | select(.ci_rollup=="FAIL" and .isDraft==false)] | length' "$OUT_JSON")
[ "$nonblocker_fails" -eq 0 ]
