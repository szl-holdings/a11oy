#!/usr/bin/env bash
# =============================================================================
# check_private_ip_leak.sh — CI gate: no private/internal addresses in SERVED code
# =============================================================================
# SAFE-NOW hardening (2026-06-18). Ratchets the egress-leak class shut: private
# tailnet IPs, the self-hosted box IP, and internal inference ports must NEVER
# appear in code paths that are SERVED to the browser (web/, static/, pages/,
# templates/, assets/). This is the same leak class scrubbed by hand in #492-#499;
# this gate makes a regression a red build instead of a silent egress leak.
#
# What it FAILS on (in served paths only):
#   - Tailnet CGNAT range 100.64.0.0/10  (regex 100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.)
#   - The self-hosted box IP 167.233.50.75
#   - The internal inference port :11434 (Ollama) and :9471
#
# Legitimate, intentionally-public references are allow-listed by exact
# "path:token" pairs in scripts/private_ip_leak_allowlist.txt (honest exceptions
# only — e.g. the DNS-roadmap page that documents the public box IP, or a
# third-party Ollama localhost example). The allowlist is data, never a code
# change to the matcher.
#
# Usage:
#   bash scripts/check_private_ip_leak.sh            # scan the served tree
#   SERVED_PATHS="web static" bash scripts/...        # override scan roots
#   ALLOWLIST_FILE=/path bash scripts/...             # override allowlist
#
# Exit codes:  0 = clean   1 = leak found   2 = config error
# =============================================================================
set -euo pipefail

# Directories that are served to the browser. Override via SERVED_PATHS.
SERVED_PATHS="${SERVED_PATHS:-web static pages templates assets}"

# Allowlist of honest exceptions (one "relative/path:offending-substring" per line;
# blank lines and #-comments ignored).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALLOWLIST_FILE="${ALLOWLIST_FILE:-${SCRIPT_DIR}/private_ip_leak_allowlist.txt}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo "[INFO]  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]  $*${NC}"; }
log_error() { echo -e "${RED}[ERROR] $*${NC}"; }
log_ok()    { echo -e "${GREEN}[OK]    $*${NC}"; }

# ---------------------------------------------------------------------------
# Leak patterns (extended regex, case-insensitive). Each is a distinct class.
# ---------------------------------------------------------------------------
PATTERNS=(
  '100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]+\.[0-9]+'   # tailnet 100.64/10
  '167\.233\.50\.75'                                              # self-hosted box IP
  ':11434'                                                        # internal Ollama port
  ':9471'                                                         # internal inference port
)
# A single alternation for one grep pass.
COMBINED="$(IFS='|'; echo "${PATTERNS[*]}")"

# ---------------------------------------------------------------------------
# Load the allowlist into an associative set keyed by "path:substring".
# ---------------------------------------------------------------------------
declare -A ALLOW
if [[ -f "$ALLOWLIST_FILE" ]]; then
  while IFS= read -r line; do
    line="${line%%#*}"                       # strip trailing comments
    line="$(echo "$line" | sed 's/[[:space:]]*$//;s/^[[:space:]]*//')"
    [[ -z "$line" ]] && continue
    ALLOW["$line"]=1
  done < "$ALLOWLIST_FILE"
  log_info "Loaded ${#ALLOW[@]} allowlist entr$([[ ${#ALLOW[@]} -eq 1 ]] && echo y || echo ies) from ${ALLOWLIST_FILE}"
else
  log_warn "No allowlist file at ${ALLOWLIST_FILE} (proceeding with zero exceptions)"
fi

# Build a `find` over the existing served roots.
ROOTS=()
for d in $SERVED_PATHS; do
  [[ -d "$d" ]] && ROOTS+=("$d")
done
if [[ ${#ROOTS[@]} -eq 0 ]]; then
  log_warn "None of the served paths exist here (${SERVED_PATHS}); nothing to scan."
  exit 0
fi
log_info "Scanning served paths: ${ROOTS[*]}"
log_info "Leak patterns: tailnet 100.64/10, 167.233.50.75, :11434, :9471"

# ---------------------------------------------------------------------------
# Scan. grep -rIn over the roots; every hit is checked against the allowlist.
# `:%token` is the exact offending matched substring per line.
# ---------------------------------------------------------------------------
LEAKS=0
LEAK_REPORT=""

# -I skips binary files; -E extended regex; -o would lose line numbers, so we
# re-extract the matched token per hit for an exact allowlist key.
while IFS= read -r hit; do
  [[ -z "$hit" ]] && continue
  file="${hit%%:*}"
  rest="${hit#*:}"
  lineno="${rest%%:*}"
  # The exact matched substring (first match on the line).
  token="$(echo "$hit" | grep -oiE "$COMBINED" | head -n1)"
  key="${file}:${token}"
  if [[ -n "${ALLOW[$key]:-}" ]]; then
    continue   # honest, documented exception
  fi
  LEAKS=1
  LEAK_REPORT="${LEAK_REPORT}\n  ${file}:${lineno}  →  ${token}"
done < <(grep -rInE "$COMBINED" "${ROOTS[@]}" 2>/dev/null || true)

# ---------------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------------
if [[ $LEAKS -eq 1 ]]; then
  log_error "==============================================================="
  log_error "PRIVATE-IP / INTERNAL-ENDPOINT LEAK in SERVED code paths"
  log_error "==============================================================="
  echo -e "${RED}Offending references (private tailnet IP / box IP / internal port):${NC}"
  echo -e "$LEAK_REPORT"
  echo ""
  echo "Served code must never expose private/internal addresses. Fix by scrubbing"
  echo "the address at egress (see szl_backend_hardening.py), OR — if the reference"
  echo "is intentionally public (e.g. the DNS-roadmap page documenting the public"
  echo "box IP) — add an honest 'path:token' line to:"
  echo "    ${ALLOWLIST_FILE}"
  exit 1
else
  log_ok "No private-IP / internal-endpoint leaks in served paths."
  exit 0
fi
