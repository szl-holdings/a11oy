#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# verify_all.sh — Top-level verifier. Runs every check, including PhD defects.
. "$(dirname "$0")/_lib.sh"
require_gh; require_jq; require_curl

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUMMARY="$OUT_DIR/verify_all_summary.md"
: > "$SUMMARY"
FAIL=0

run_step() {
  local label="$1"; shift
  hdr "$label"
  if "$@"; then
    ok "$label PASSED"; echo "- ✅ $label" >> "$SUMMARY"
  else
    err "$label FAILED"; echo "- ❌ $label" >> "$SUMMARY"; FAIL=$((FAIL+1))
  fi
}

{
  echo "# Replit Hardcode Payload — Verify Summary"
  echo
  echo "Generated: $(date -u +%FT%TZ)"
  echo "Operator: $SZL_OPERATOR_NAME <$SZL_OPERATOR_EMAIL>"
  echo
} >> "$SUMMARY"

run_step "Refresh PR state"                              "$SCRIPT_DIR/pull_pr_state.sh"
run_step "CI status across org"                          "$SCRIPT_DIR/check_ci_status.sh"
run_step "Doctrine V6 forbidden-pattern sweep"           "$SCRIPT_DIR/check_doctrine.sh"
run_step "Anatomy figures present on every branch"       "$SCRIPT_DIR/verify_anatomy_pushes.sh"
run_step "DOI gate fix lives in PR branches"             "$SCRIPT_DIR/verify_doi_gate_fix.sh"
run_step "Zenodo DOI reachability (12 DOIs)"             "$SCRIPT_DIR/check_zenodo_dois.sh"
run_step "PhD audit defect ratchet (D1-D18)"             "$SCRIPT_DIR/check_phd_defects.sh"

echo
echo "================================================================="
echo "  SUMMARY: $((7-FAIL))/7 checks passed"
echo "================================================================="
cat "$SUMMARY"
echo
log "Full summary: $SUMMARY"
[ "$FAIL" -eq 0 ]
