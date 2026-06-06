#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# pull_pr_state.sh — Refresh the live state of every open PR across the org.
# Output: data/all_open_prs.json (overwrites)

. "$(dirname "$0")/_lib.sh"
require_gh
require_jq

hdr "Refreshing all open PRs across $SZL_ORG"

OUT="$DATA_DIR/all_open_prs.json"
TMP=$(mktemp)
echo '[' > "$TMP"
FIRST=1

for repo in "${SZL_REPOS[@]}"; do
  log "Fetching open PRs for $SZL_ORG/$repo ..."
  prs=$(gh pr list --repo "$SZL_ORG/$repo" --state open \
    --json number,title,headRefName,baseRefName,isDraft,mergeable,mergeStateStatus,createdAt,updatedAt,author,labels,statusCheckRollup,url \
    2>/dev/null || echo "[]")
  count=$(echo "$prs" | jq 'length')
  if [ "$count" -eq 0 ]; then
    ok "$repo: 0 open"
    continue
  fi
  ok "$repo: $count open"
  echo "$prs" | jq --arg repo "$repo" '.[] | . + {repo:$repo}' | while IFS= read -r line; do
    if [ "$FIRST" -eq 1 ]; then FIRST=0; else echo ',' >> "$TMP"; fi
    echo "$line" >> "$TMP"
  done
  # FIRST flag: rewrite via marker
  FIRST=$(jq 'length' "$OUT" 2>/dev/null || echo 0)
  if [ "$FIRST" = "0" ]; then FIRST=0; else FIRST=1; fi
done

# Simpler: just collect into one big array
echo '[' > "$TMP"
sep=""
for repo in "${SZL_REPOS[@]}"; do
  prs=$(gh pr list --repo "$SZL_ORG/$repo" --state open \
    --json number,title,headRefName,baseRefName,isDraft,mergeable,mergeStateStatus,createdAt,updatedAt,author,labels,statusCheckRollup,url \
    2>/dev/null || echo "[]")
  cnt=$(echo "$prs" | jq 'length')
  [ "$cnt" -eq 0 ] && continue
  enriched=$(echo "$prs" | jq --arg repo "$repo" '[.[] | . + {repo:$repo}]')
  rows=$(echo "$enriched" | jq -c '.[]')
  while IFS= read -r row; do
    [ -z "$row" ] && continue
    printf '%s%s\n' "$sep" "$row" >> "$TMP"
    sep=","
  done <<< "$rows"
done
echo ']' >> "$TMP"

if jq empty < "$TMP" 2>/dev/null; then
  jq '.' "$TMP" > "$OUT"
  total=$(jq 'length' "$OUT")
  ok "Wrote $OUT — $total open PRs"
else
  err "Failed to assemble JSON. See $TMP"
  exit 1
fi
rm -f "$TMP"
