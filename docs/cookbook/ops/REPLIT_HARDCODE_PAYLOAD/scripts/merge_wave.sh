#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# merge_wave.sh — Execute one of the 5 merge waves from UNIFIED_OPERATOR_HANDOFF.md.
# OPERATOR-ONLY. Will refuse to run unless caller passes --i-am-the-operator.
#
# Usage:
#   ./merge_wave.sh --wave 1 --i-am-the-operator         # dry-run by default
#   ./merge_wave.sh --wave 1 --i-am-the-operator --execute
#
# Wave inventory (see docs/UNIFIED_OPERATOR_HANDOFF.md for canonical list):
#   1 — hygiene PRs (41)
#   2 — scorecard / security (7)
#   3 — CI wire baseline (3)
#   4 — Fly V9 fleet (9)
#   5 — tail-end (anatomy, DOI gate, thesis)

. "$(dirname "$0")/_lib.sh"
require_gh
require_jq

WAVE=""
OPERATOR=0
EXECUTE=0

while [ $# -gt 0 ]; do
  case "$1" in
    --wave) WAVE="$2"; shift 2;;
    --i-am-the-operator) OPERATOR=1; shift;;
    --execute) EXECUTE=1; shift;;
    *) err "Unknown arg: $1"; exit 2;;
  esac
done

if [ "$OPERATOR" -ne 1 ]; then
  err "Refusing to run. CTO authority does not include merging."
  err "Only Stephen P. Lutar Jr. as repo admin can run this. Pass --i-am-the-operator if that's you."
  exit 1
fi

case "$WAVE" in
  1)
    LABEL="hygiene"
    # Hygiene PRs were opened by the PM/GHX subagents. Use label or naming convention.
    QUERY='label:hygiene OR title:"chore: add"'
    ;;
  2)
    LABEL="scorecard_security"
    PRS=("\.github:37" "vsp-otel:6" "vsp-otel:7" "vsp-otel:8" "agi-forecast:6" "agi-forecast:7" "agi-forecast:8" "szl-trust:13" "szl-cookbook:12" "szl-brand:16" "lutar-lean:19")
    ;;
  3)
    LABEL="ci_wire"
    PRS=("vsp-otel:5" "agi-forecast:5" ".github:36")
    ;;
  4)
    LABEL="fly_v9_fleet"
    PRS=("ouroboros:31" "ouroboros:32" "sentra:22" "vsp-otel:4" "agi-forecast:4" "lutar-lean:18" "ouroboros-thesis:44" "szl-brand:15" ".github:35")
    ;;
  5)
    LABEL="tail_end"
    PRS=("ouroboros:28" "ouroboros-thesis:38" "szl-trust:11" "ouroboros:29" "ouroboros-thesis:39" "ouroboros-thesis:46")
    ;;
  *)
    err "Usage: merge_wave.sh --wave {1|2|3|4|5} --i-am-the-operator [--execute]"
    exit 2
    ;;
esac

hdr "Wave $WAVE: $LABEL"
log "Mode: $([ "$EXECUTE" -eq 1 ] && echo EXECUTE || echo DRY-RUN)"

if [ "${#PRS[@]:-0}" -gt 0 ]; then
  for entry in "${PRS[@]}"; do
    IFS=':' read -r repo num <<< "$entry"
    info=$(gh pr view "$num" --repo "$SZL_ORG/$repo" --json title,isDraft,mergeStateStatus,statusCheckRollup 2>/dev/null || echo '{}')
    title=$(echo "$info" | jq -r '.title // "?"')
    draft=$(echo "$info" | jq -r '.isDraft // false')
    state=$(echo "$info" | jq -r '.mergeStateStatus // "?"')
    log "$repo#$num [$state, draft=$draft] $title"
    if [ "$EXECUTE" -eq 1 ]; then
      if [ "$draft" = "true" ]; then
        gh pr ready "$num" --repo "$SZL_ORG/$repo" && ok "Marked ready: $repo#$num"
      fi
      if gh pr merge "$num" --repo "$SZL_ORG/$repo" --squash --auto --delete-branch; then
        ok "Queued merge: $repo#$num"
      else
        err "Failed to merge: $repo#$num"
      fi
    fi
  done
else
  warn "Wave $WAVE uses a label/title query — review UNIFIED_OPERATOR_HANDOFF.md and merge interactively."
fi

[ "$EXECUTE" -eq 1 ] || warn "Dry-run only. Re-run with --execute to actually merge."
