#!/usr/bin/env bash
# =============================================================================
# check_namespace_leak.sh — CI namespace hygiene gate
# =============================================================================
# Doctrine v7 §14: orchestrator-mediated cross-namespace writes must be
# attributed. This script prevents personal-namespace references from entering
# the SZLHOLDINGS org codebase via PR.
#
# Usage (in GitHub Actions):
#   bash check_namespace_leak.sh [--base <base-ref>] [--head <head-ref>]
#
# Exit codes:
#   0 — no leaks found
#   1 — namespace leaks detected (fail the PR)
#   2 — configuration error
#
# Configurable via environment variables:
#   PERSONAL_NAMESPACES     Space-separated list of banned namespaces
#   ALLOWED_PATHS           Colon-separated glob patterns to exclude from scan
#   SCAN_EXTENSIONS         Comma-separated file extensions to scan
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Add any additional personal namespaces here (space-separated)
PERSONAL_NAMESPACES="${PERSONAL_NAMESPACES:-betterwithage}"

# File extensions to check (can be overridden)
SCAN_EXTENSIONS="${SCAN_EXTENSIONS:-py,yml,yaml,json,md,sh,ts,js,toml,cfg,ini,txt,dockerfile,Makefile}"

# Paths to always exclude from scanning (colon-separated globs)
ALLOWED_PATHS="${ALLOWED_PATHS:-CHANGELOG.md:REPORT.md:*SWEEP*.md:*AUDIT*.md:*audit*:check_namespace_leak.sh}"

# Base ref for diff (default: main)
BASE_REF="${BASE_REF:-origin/main}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info()  { echo "[INFO]  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]  $*${NC}"; }
log_error() { echo -e "${RED}[ERROR] $*${NC}"; }
log_ok()    { echo -e "${GREEN}[OK]    $*${NC}"; }

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE_REF="$2"; shift 2 ;;
    --head) HEAD_REF="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# ---------------------------------------------------------------------------
# Build the grep pattern from PERSONAL_NAMESPACES
# ---------------------------------------------------------------------------

IFS=' ' read -ra NS_ARRAY <<< "$PERSONAL_NAMESPACES"

# Build alternation pattern for grep: (ns1|ns2|...)
PATTERN=""
for ns in "${NS_ARRAY[@]}"; do
  # Match personal namespaces in common reference contexts:
  #   huggingface.co/<ns>/   hf.co/<ns>/   github.com/<ns>/
  #   author="<ns>"  author: <ns>  owner=<ns>
  #   <ns>/<repo>  (bare reference)
  NS_PATTERN="(huggingface\.co/${ns}|hf\.co/${ns}|github\.com/${ns}|author=\"${ns}\"|author:\s*${ns}|owner=${ns}|\"${ns}/|'${ns}/)"
  if [[ -z "$PATTERN" ]]; then
    PATTERN="$NS_PATTERN"
  else
    PATTERN="${PATTERN}|${NS_PATTERN}"
  fi
done

# Also catch bare namespace/repo references
BARE_PATTERN=""
for ns in "${NS_ARRAY[@]}"; do
  if [[ -z "$BARE_PATTERN" ]]; then
    BARE_PATTERN="${ns}/"
  else
    BARE_PATTERN="${BARE_PATTERN}|${ns}/"
  fi
done

COMBINED_PATTERN="(${PATTERN})"

# ---------------------------------------------------------------------------
# Determine files to scan
# ---------------------------------------------------------------------------

log_info "Namespace leak check starting"
log_info "Banned namespaces: ${PERSONAL_NAMESPACES}"
log_info "Base ref: ${BASE_REF}"

# Prefer scanning only changed files in the PR diff
CHANGED_FILES=""
if git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1; then
  CHANGED_FILES=$(git diff --name-only "${BASE_REF}"...HEAD 2>/dev/null || true)
  log_info "Scanning $(echo "$CHANGED_FILES" | wc -l | tr -d ' ') changed files vs ${BASE_REF}"
else
  log_warn "Cannot resolve ${BASE_REF} — scanning all tracked files instead"
  CHANGED_FILES=$(git ls-files)
fi

if [[ -z "$CHANGED_FILES" ]]; then
  log_ok "No files to scan."
  exit 0
fi

# ---------------------------------------------------------------------------
# Build extension filter
# ---------------------------------------------------------------------------

EXT_INCLUDES=""
IFS=',' read -ra EXT_ARRAY <<< "$SCAN_EXTENSIONS"
for ext in "${EXT_ARRAY[@]}"; do
  EXT_INCLUDES="${EXT_INCLUDES} --include=*.${ext}"
done

# ---------------------------------------------------------------------------
# Build exclusion list from ALLOWED_PATHS
# ---------------------------------------------------------------------------

EXCLUDE_ARGS=""
IFS=':' read -ra EXCL_ARRAY <<< "$ALLOWED_PATHS"
for excl in "${EXCL_ARRAY[@]}"; do
  EXCLUDE_ARGS="${EXCLUDE_ARGS} --exclude=${excl}"
done

# ---------------------------------------------------------------------------
# Run the scan
# ---------------------------------------------------------------------------

LEAK_FOUND=0
LEAK_DETAILS=""

while IFS= read -r file; do
  # Skip if file does not exist (deleted in this PR)
  [[ -f "$file" ]] || continue

  # Skip excluded paths
  skip=0
  for excl in "${EXCL_ARRAY[@]}"; do
    # shellcheck disable=SC2254
    case "$file" in
      $excl) skip=1; break ;;
      */$excl) skip=1; break ;;
    esac
  done
  [[ $skip -eq 1 ]] && continue

  # Check extension
  ext="${file##*.}"
  ext_match=0
  for allowed_ext in "${EXT_ARRAY[@]}"; do
    if [[ "$ext" == "$allowed_ext" ]] || [[ "${file,,}" == "dockerfile" ]] || [[ "${file,,}" == "makefile" ]]; then
      ext_match=1; break
    fi
  done
  [[ $ext_match -eq 0 ]] && continue

  # Grep for personal namespace references
  matches=$(grep -nEi "$COMBINED_PATTERN" "$file" 2>/dev/null || true)
  if [[ -n "$matches" ]]; then
    LEAK_FOUND=1
    LEAK_DETAILS="${LEAK_DETAILS}\n--- ${file} ---\n${matches}\n"
  fi
done <<< "$CHANGED_FILES"

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

if [[ $LEAK_FOUND -eq 1 ]]; then
  log_error "==========================================================="
  log_error "NAMESPACE LEAK DETECTED — PR must not merge until resolved"
  log_error "==========================================================="
  echo ""
  echo -e "${RED}Personal namespace references found in PR diff:${NC}"
  echo -e "$LEAK_DETAILS"
  echo ""
  echo "Doctrine v7 §14: orchestrator-mediated cross-namespace writes must be"
  echo "attributed. Personal namespace references ('${PERSONAL_NAMESPACES}') must"
  echo "not appear in SZLHOLDINGS org code except in:"
  echo "  - Audit/sweep reports (excluded via ALLOWED_PATHS)"
  echo "  - This CI script itself"
  echo ""
  echo "Fix: Replace '${PERSONAL_NAMESPACES}/<repo>' with 'SZLHOLDINGS/<repo>'"
  echo "     or add the file to ALLOWED_PATHS if it is a legitimate exception."
  echo ""
  echo "For HuggingFace token scope issues: rotate Cursor's HF_TOKEN to one"
  echo "scoped only to the SZLHOLDINGS org (Settings → Access Tokens → Fine-grained)."
  exit 1
else
  log_ok "No personal namespace leaks detected in changed files."
  log_ok "All ${PERSONAL_NAMESPACES} references are clean."
  exit 0
fi
