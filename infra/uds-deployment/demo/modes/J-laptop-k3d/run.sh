#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode J — DU has no infra; show it on the laptop (k3d). THE DEFAULT MODE.
# Founder directive 2026-05-30 16:46 EDT.
#
# Thin wrapper: runs the real, existing warhacker/usb/fallback/offline-deploy.sh
# (pinned k3d + signed vessels Zarf) on Stephen's Lenovo Yoga (Win 11 + WSL2).
# If Docker/k3d is unavailable, points to Path C (offline fixtures, real crypto).
#
# Usage:
#   run.sh --usb /path/to/usb [--platform linux-amd64] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode J — laptop k3d (DEFAULT if DU gives no access).
  --usb PATH          (required) path to warhacker/usb payload root
  --platform NAME     linux-amd64 (default; WSL2) | darwin-arm64
  --dry-run
Pre-travel: set WSL2 .wslconfig memory=24GB and soak-test (see
  warhacker/HARDWARE_RECOMMENDATIONS_2026-05-30.md). Watch the Lunar-Lake 37W cap.
USAGE
}

USB="" PLATFORM="linux-amd64"
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --usb) USB="${2:-}"; shift 2;;
    --platform) PLATFORM="${2:-}"; shift 2;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done
[ -n "${USB}" ] || { err "--usb is required (path to warhacker/usb)"; usage; exit "${EC_USAGE}"; }
[ -d "${USB}" ] || die "USB path not a directory: ${USB}" "${EC_PRECOND}"
need_file "${USB}/fallback/offline-deploy.sh"

fa001_banner
export PLATFORM
export PATH="${USB}/bin/${PLATFORM}:${PATH}"
log "Mode J — laptop k3d. PLATFORM=${PLATFORM}."

if ! command -v docker >/dev/null 2>&1; then
  warn "Docker not on PATH. Skip k3d. Go Path C (offline fixtures, real crypto):"
  warn "  cd ${USB}/scenarios && OFFLINE=true ./scenario_drone_loses_contact.sh && ./scenario_tamper_test.sh"
  exit "${EC_PRECOND}"
fi

log "1. Bring up pinned k3d + deploy signed vessels Zarf (real offline path)"
run "${USB}/fallback/offline-deploy.sh"
log "2. Run governed-DENY + tamper scenarios:"
log "   cd ${USB}/scenarios && ./scenario_drone_loses_contact.sh && ./scenario_tamper_test.sh"
log "3. Teardown after rehearsal: k3d cluster delete szl-warhacker-recovery"
log "DONE — Mode J. Vessels + Pepr live on the laptop. Four modules staged (FA-001)."
exit "${EC_OK}"
