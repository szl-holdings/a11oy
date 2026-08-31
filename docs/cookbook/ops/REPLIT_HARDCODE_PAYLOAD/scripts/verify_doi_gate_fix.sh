#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# verify_doi_gate_fix.sh — Confirm the DOI-title gate fix lives in 3 PRs
# AND that the underlying curl test resolves a concept DOI correctly.

. "$(dirname "$0")/_lib.sh"
require_gh
require_jq
require_curl

hdr "Verifying DOI gate fix"

EXPECTED_FIX_SHA=(
  "ouroboros:28:7d8f1f3"
  "ouroboros-thesis:38:c32321f"
  "szl-trust:11:e0e6893"
)

OUT="$OUT_DIR/doi_gate_verify.md"
{
  echo "# DOI Gate Fix Verification"
  echo
  echo "Generated: $(date -u +%FT%TZ)"
  echo
} > "$OUT"

# 1. Confirm each PR branch has the expected commit prefix
echo "## PR commit presence" >> "$OUT"
echo >> "$OUT"
echo "| PR | Expected SHA prefix | Found? |" >> "$OUT"
echo "|----|---------------------|--------|" >> "$OUT"

FAILS=0
for spec in "${EXPECTED_FIX_SHA[@]}"; do
  IFS=':' read -r repo num pref <<< "$spec"
  commits=$(gh pr view "$num" --repo "$SZL_ORG/$repo" --json commits -q '[.commits[].oid]' 2>/dev/null || echo "[]")
  if echo "$commits" | jq -e --arg p "$pref" 'any(startswith($p))' >/dev/null 2>&1; then
    ok "$repo#$num has commit $pref"
    printf '| %s#%s | %s | ✅ |\n' "$repo" "$num" "$pref" >> "$OUT"
  else
    err "$repo#$num MISSING commit $pref"
    printf '| %s#%s | %s | ❌ |\n' "$repo" "$num" "$pref" >> "$OUT"
    FAILS=$((FAILS+1))
  fi
done

# 2. Live curl test on a known concept DOI
echo >> "$OUT"
echo "## Live Zenodo concept-DOI follow test" >> "$OUT"
echo >> "$OUT"
echo "Concept DOI 19944926 should redirect to a versioned record. We use the same flags as the gate." >> "$OUT"
echo >> "$OUT"

set +e
resp=$(curl -sSL -H "Accept: application/json" "https://zenodo.org/api/records/19944926" 2>/dev/null)
set -e

if echo "$resp" | jq -e '.metadata.title' >/dev/null 2>&1; then
  title=$(echo "$resp" | jq -r '.metadata.title')
  doi=$(echo "$resp" | jq -r '.doi // .metadata.doi // empty')
  ok "Concept DOI resolved. Title: $title"
  echo "- ✅ Resolved title: \`$title\`" >> "$OUT"
  echo "- DOI: \`$doi\`" >> "$OUT"
else
  err "Concept-DOI follow FAILED. Response is not JSON or missing metadata."
  echo "- ❌ Live test failed." >> "$OUT"
  FAILS=$((FAILS+1))
fi

# 3. CI status on the 3 PRs
echo >> "$OUT"
echo "## PR CI status" >> "$OUT"
echo >> "$OUT"
echo "| PR | Status |" >> "$OUT"
echo "|----|--------|" >> "$OUT"
for spec in "${EXPECTED_FIX_SHA[@]}"; do
  IFS=':' read -r repo num pref <<< "$spec"
  status=$(gh pr view "$num" --repo "$SZL_ORG/$repo" --json statusCheckRollup -q \
    '[.statusCheckRollup[]?.conclusion] | if any(.=="FAILURE") then "FAIL"
     elif any(.=="PENDING") then "PENDING"
     elif all(.=="SUCCESS" or .=="NEUTRAL" or .=="SKIPPED" or .==null) then "PASS"
     else "MIXED" end' 2>/dev/null || echo "?")
  printf '| %s#%s | %s |\n' "$repo" "$num" "$status" >> "$OUT"
done

log "Report: $OUT"
[ "$FAILS" -eq 0 ]
