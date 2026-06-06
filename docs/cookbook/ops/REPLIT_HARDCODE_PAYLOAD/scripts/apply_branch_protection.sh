#!/usr/bin/env bash
# Branch protection hardening script for all 14 szl-holdings repos.
# OPERATOR-ONLY: requires admin BP authority. CTO cannot run this.
#
# Closes Scorecard BranchProtectionID across the org. Expected score uplift: +1.0
#
# Usage:
#   ./scripts/apply_branch_protection.sh --dry-run    # show what would change
#   ./scripts/apply_branch_protection.sh --execute    # actually apply (operator)

set -euo pipefail

REPOS="amaru a11oy sentra terra vessels counsel carlota-jo ouroboros ouroboros-thesis lutar-lean szl-trust szl-cookbook szl-brand .github"

MODE="${1:---dry-run}"

if [ "$MODE" != "--execute" ] && [ "$MODE" != "--dry-run" ]; then
  echo "Usage: $0 [--dry-run|--execute]"
  exit 1
fi

for r in $REPOS; do
  echo
  echo "=== $r ==="
  if [ "$MODE" = "--dry-run" ]; then
    cur=$(gh api "/repos/szl-holdings/$r/branches/main/protection" 2>/dev/null || echo "{}")
    enforce=$(echo "$cur" | jq -r '.enforce_admins.enabled // false')
    reviews=$(echo "$cur" | jq -r '.required_pull_request_reviews.required_approving_review_count // 0')
    echo "  current: enforce_admins=$enforce reviews=$reviews"
    echo "  would set: enforce_admins=true reviews=2 dismiss_stale=true codeowners=true require_last_push=true"
    continue
  fi

  # EXECUTE mode
  gh api -X PUT "/repos/szl-holdings/$r/branches/main/protection" \
    --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "contexts": []
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON
  echo "  [ok] $r main branch protection updated"
done

echo
echo "Done. Re-run Scorecard to see BranchProtectionID close:"
echo "  for r in $REPOS; do gh workflow run scorecard.yml --repo szl-holdings/\$r; done"
