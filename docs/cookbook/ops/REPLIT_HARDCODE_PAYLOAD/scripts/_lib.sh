# SPDX-License-Identifier: Apache-2.0
# Shared library for Replit Operator Payload scripts.
# Source this from every script: `. "$(dirname "$0")/_lib.sh"`

set -uo pipefail

# -----------------------------------------------------------------------------
# Identity (immutable)
# -----------------------------------------------------------------------------
export SZL_OPERATOR_NAME="Stephen P. Lutar Jr."
export SZL_OPERATOR_EMAIL="stephen@szlholdings.com"
export SZL_OPERATOR_ORCID="0009-0001-0110-4173"
export SZL_OPERATOR_GH="stephenlutar2-hash"
export SZL_ORG="szl-holdings"

# -----------------------------------------------------------------------------
# Repo universe (14 public + agi-forecast + vsp-otel = 16 repos that matter)
# -----------------------------------------------------------------------------
export SZL_REPOS=(
  amaru a11oy sentra terra vessels counsel carlota-jo
  ouroboros ouroboros-thesis lutar-lean
  szl-trust szl-cookbook szl-brand .github
  agi-forecast vsp-otel
)

# -----------------------------------------------------------------------------
# Doctrine V6 — forbidden patterns (case-insensitive)
# -----------------------------------------------------------------------------
export SZL_FORBIDDEN_PATTERNS=(
  "AlloyScape"
  "Glass Wing"
  "Glasswing"
  "Mythos"
  "Stephen Paul"
  "Perplexity Computer"
  "anonymous"
)

# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
export PAYLOAD_ROOT="${PAYLOAD_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export DATA_DIR="$PAYLOAD_ROOT/data"
export OUT_DIR="${OUT_DIR:-$PAYLOAD_ROOT/out}"
mkdir -p "$OUT_DIR"

# -----------------------------------------------------------------------------
# Colors
# -----------------------------------------------------------------------------
if [ -t 1 ]; then
  C_RED=$'\033[31m'; C_GREEN=$'\033[32m'; C_YEL=$'\033[33m'
  C_BLU=$'\033[34m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_RST=$'\033[0m'
else
  C_RED=""; C_GREEN=""; C_YEL=""; C_BLU=""; C_DIM=""; C_BOLD=""; C_RST=""
fi

log()   { printf '%s[%s]%s %s\n' "$C_DIM" "$(date -u +%H:%M:%SZ)" "$C_RST" "$*" >&2; }
ok()    { printf '%s✓%s %s\n' "$C_GREEN" "$C_RST" "$*" >&2; }
warn()  { printf '%s⚠%s %s\n' "$C_YEL"  "$C_RST" "$*" >&2; }
err()   { printf '%s✗%s %s\n' "$C_RED"  "$C_RST" "$*" >&2; }
hdr()   { printf '\n%s%s== %s ==%s\n' "$C_BOLD" "$C_BLU" "$*" "$C_RST" >&2; }

# -----------------------------------------------------------------------------
# Auth / prereq checks
# -----------------------------------------------------------------------------
require_gh() {
  if ! command -v gh >/dev/null 2>&1; then
    err "GitHub CLI (gh) is not installed. Install: https://cli.github.com/"
    exit 127
  fi
  # gh auth status is sometimes stale — verify by hitting /user.
  if ! gh api /user >/dev/null 2>&1; then
    err "GitHub CLI not authenticated. Run: gh auth login --git-protocol https --web"
    err "Or set: export GH_TOKEN=ghp_..."
    exit 1
  fi
  local who
  who=$(gh api /user --jq '.login')
  log "Authenticated as: $who"
  if [ "$who" != "$SZL_OPERATOR_GH" ]; then
    warn "Logged in as '$who' — expected '$SZL_OPERATOR_GH'. Continuing anyway."
  fi
}

require_jq() {
  command -v jq >/dev/null 2>&1 || { err "jq required. Install: apt-get install -y jq"; exit 127; }
}

require_curl() {
  command -v curl >/dev/null 2>&1 || { err "curl required."; exit 127; }
}
