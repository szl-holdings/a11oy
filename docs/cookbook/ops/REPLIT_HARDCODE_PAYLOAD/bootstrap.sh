#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# bootstrap.sh — Entry point when this payload boots on Replit.
# Prints a status dashboard, surfaces any missing prereqs, and shows the next
# operator action.

set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
. "$ROOT/scripts/_lib.sh"

clear || true
cat <<BANNER
$C_BOLD$C_BLU
╔══════════════════════════════════════════════════════════════════════╗
║         SZL Holdings — Replit Operator Payload                       ║
║         Operator: Stephen P. Lutar Jr. <stephen@szlholdings.com>     ║
║         ORCID: 0009-0001-0110-4173                                    ║
║         Doctrine V6 — public-only, Λ ≥ 0.90 conjunctive MIN           ║
╚══════════════════════════════════════════════════════════════════════╝
$C_RST
BANNER

hdr "Step 1 — Prereq check"

missing=()
for bin in gh jq curl git; do
  if command -v "$bin" >/dev/null 2>&1; then
    ok "$bin: $(command -v "$bin")"
  else
    err "$bin: MISSING"
    missing+=("$bin")
  fi
done

if [ "${#missing[@]}" -gt 0 ]; then
  warn "Install missing tools. On Replit (Nix): they should be in replit.nix."
  exit 1
fi

hdr "Step 2 — GitHub auth"
if gh api /user >/dev/null 2>&1; then
  who=$(gh api /user --jq '.login')
  ok "Authenticated as $who"
else
  err "gh is not authenticated."
  cat <<EOT
  Run:
    gh auth login --git-protocol https --web
  Or export a fine-grained PAT:
    export GH_TOKEN=ghp_...
  Required scopes: repo, read:org, workflow, security_events
EOT
  exit 1
fi

hdr "Step 3 — Live PR state"
log "Refreshing data/all_open_prs.json from GitHub ..."
"$ROOT/scripts/pull_pr_state.sh" || warn "pull_pr_state.sh returned non-zero"

total=$(jq 'length' "$DATA_DIR/all_open_prs.json" 2>/dev/null || echo 0)
ok "Live open PRs across $SZL_ORG: $total"

hdr "Step 4 — Verifier menu"
cat <<MENU
  Available actions:

  1) Full verification suite     ./scripts/verify_all.sh
  2) CI status only              ./scripts/check_ci_status.sh
  3) Doctrine V6 sweep           ./scripts/check_doctrine.sh
  4) Anatomy push verify         ./scripts/verify_anatomy_pushes.sh
  5) DOI gate fix verify         ./scripts/verify_doi_gate_fix.sh
  6) Zenodo DOI reachability     ./scripts/check_zenodo_dois.sh
  7) PhD defect ratchet (D1-D18) ./scripts/check_phd_defects.sh
  7) Refresh PR state            ./scripts/pull_pr_state.sh
  9) Operator merge wave         ./scripts/merge_wave.sh --wave N --i-am-the-operator [--execute]

  Reports drop into: $OUT_DIR

  Read first:
    docs/UNIFIED_OPERATOR_HANDOFF.md     — 5-wave merge plan
    docs/OPERATOR_QUICKSTART.md          — fast path
    docs/CTO_AUTHORITY.md                — what CTO can / cannot do
MENU

ok "Bootstrap complete. Run option 1 to verify everything."
