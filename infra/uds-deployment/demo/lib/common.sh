#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# demo/lib/common.sh — shared helpers for the Warhacker jack-in toolkit.
# Founder directive 2026-05-30 16:46 EDT: real demo, no mocks, flex on the fly.
#
# Portability: bash 4+/5+ only (works on Stephen's Lenovo Yoga, Win 11 + WSL2).
# No zsh-isms, no associative-array exotica beyond bash 4, no `mapfile -d` reliance.
#
# Sourced by every mode script. Provides: logging, fail-fast guards, dry-run,
# and the FA-001 honesty banner.

set -o errexit
set -o nounset
set -o pipefail

# ── Exit codes (stable contract for the toolkit) ──────────────────────────────
readonly EC_OK=0
readonly EC_USAGE=2          # bad/missing arguments
readonly EC_PRECOND=3        # a precondition is not met (e.g. Mode A before D)
readonly EC_MISSING_TOOL=4   # a required CLI is not on PATH
readonly EC_CLUSTER=5        # cluster unreachable / wrong kind
readonly EC_FA001=6          # blocked by FA-001 (image not pushed)
readonly EC_NOTIMPL=7        # documentation-only mode invoked as if runnable

# ── Dry-run flag (every script honours --dry-run) ─────────────────────────────
DRY_RUN="${DRY_RUN:-false}"

# ── Logging ───────────────────────────────────────────────────────────────────
_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }
log()  { printf '[jack-in %s] %s\n' "$(_ts)" "$*"; }
warn() { printf '[jack-in %s][WARN] %s\n' "$(_ts)" "$*" >&2; }
err()  { printf '[jack-in %s][ERROR] %s\n' "$(_ts)" "$*" >&2; }
die()  { err "$*"; exit "${2:-1}"; }

# ── "Print what we're about to do, then do it" (set -x style, but readable) ───
# Usage: run kubectl get pods -A
run() {
  printf '    + %s\n' "$*"
  if [ "${DRY_RUN}" = "true" ]; then
    printf '      (dry-run: not executed)\n'
    return 0
  fi
  "$@"
}

# ── Guards ────────────────────────────────────────────────────────────────────
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found on PATH: $1" "${EC_MISSING_TOOL}"
}

need_file() {
  [ -f "$1" ] || die "required file not found: $1" "${EC_PRECOND}"
}

# Verify kubectl is pointed at a reachable cluster.
need_cluster() {
  need_cmd kubectl
  if [ "${DRY_RUN}" = "true" ]; then
    log "dry-run: skipping live cluster reachability check"
    return 0
  fi
  kubectl cluster-info >/dev/null 2>&1 \
    || die "kubectl cannot reach a cluster — set KUBECONFIG or fix the context" "${EC_CLUSTER}"
  log "cluster reachable; current context: $(kubectl config current-context 2>/dev/null || echo '?')"
}

# Detect UDS Core by its Package CRD (uds.dev).
has_uds_core() {
  if [ "${DRY_RUN}" = "true" ]; then return 0; fi
  kubectl get crd packages.uds.dev >/dev/null 2>&1
}

# ── FA-001 honesty banner — printed by every deploy-class mode ───────────────
fa001_banner() {
  cat <<'BANNER'
  ----------------------------------------------------------------------------
  FA-001 NOTICE (read this before you narrate):
    Only the VESSELS module ships a real signed Zarf package + pullable image.
    amaru / sentra / rosie / a11oy images are NOT pushed to ghcr.io yet.
    If you point a deploy at those four, expect ImagePullBackOff. That is
    EXPECTED and HONEST. Demo vessels + the Pepr receipts controller. Never
    claim "five modules boot together."  (see docs/WARHACKER_DEMO.md / FA-001)
  ----------------------------------------------------------------------------
BANNER
}

# ── Standard --dry-run / --help parsing helper ───────────────────────────────
# Each mode calls: parse_common_flags "$@"  (it strips --dry-run, leaves the rest)
PARSED_ARGS=()
parse_common_flags() {
  PARSED_ARGS=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --dry-run) DRY_RUN="true"; shift ;;
      -h|--help) return 10 ;;   # caller prints its own usage
      *) PARSED_ARGS+=("$1"); shift ;;
    esac
  done
  return 0
}

# Repo root (two levels up from demo/lib/).
demo_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}
