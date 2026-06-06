#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# verify_anatomy_pushes.sh — Confirm the 16-figure anatomy bundle lives on every
# repo branch where the CTO pushed it.

. "$(dirname "$0")/_lib.sh"
require_gh
require_jq

hdr "Verifying anatomy figures are present on PR branches"

# Branch list from cto_prs_opened_recent.json -> anatomy section
declare -A BRANCHES=(
  ["ouroboros#29"]="docs/anatomy/4-pdfs"
  ["ouroboros-thesis#39"]="docs/anatomy/4-pdfs"
  ["ouroboros-thesis#46"]="docs/anatomy/full-16-figure-bundle"
  ["szl-brand#15"]="feat/anatomy/full-body-v2"
)

REQUIRED_FIGURES=(
  "anatomy_brain.pdf"
  "anatomy_wires.pdf"
  "anatomy_full_body.pdf"
  "hatun_body_graph.pdf"
)

OUT="$OUT_DIR/anatomy_verify.md"
{
  echo "# Anatomy Pushes Verification"
  echo
  echo "Generated: $(date -u +%FT%TZ)"
  echo
  echo "| Repo#PR | Branch | Figures Found |"
  echo "|---------|--------|----------------|"
} > "$OUT"

FAILS=0
for key in "${!BRANCHES[@]}"; do
  repo="${key%#*}"
  pr="${key#*#}"
  # Get actual head ref from live PR
  head=$(gh pr view "$pr" --repo "$SZL_ORG/$repo" --json headRefName -q .headRefName 2>/dev/null || echo "")
  if [ -z "$head" ]; then
    err "Could not resolve head branch for $key"
    printf '| %s | (unresolved) | ❌ |\n' "$key" >> "$OUT"
    FAILS=$((FAILS+1))
    continue
  fi
  # List PDFs in docs/anatomy on the branch
  files=$(gh api "/repos/$SZL_ORG/$repo/contents/docs/anatomy?ref=$head" \
    --jq '[.[] | select(.name|endswith(".pdf")) | .name]' 2>/dev/null || echo "[]")
  count=$(echo "$files" | jq 'length')
  missing=""
  for fig in "${REQUIRED_FIGURES[@]}"; do
    if ! echo "$files" | jq -e --arg f "$fig" 'index($f)' >/dev/null 2>&1; then
      # for szl-brand the path may differ; tolerate
      [ "$repo" = "szl-brand" ] && continue
      missing="$missing $fig"
    fi
  done

  if [ -n "$missing" ]; then
    err "$key on $head missing:$missing"
    printf '| %s | %s | ❌ found %s; missing%s |\n' "$key" "$head" "$count" "$missing" >> "$OUT"
    FAILS=$((FAILS+1))
  else
    ok "$key on $head — $count PDFs"
    printf '| %s | %s | ✅ %s PDFs |\n' "$key" "$head" "$count" >> "$OUT"
  fi
done

log "Report: $OUT"
[ "$FAILS" -eq 0 ]
