#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode C — bastion/SSH into an air-gapped DoD environment (USB-only deploy).
# Founder directive 2026-05-30 16:46 EDT.
#
# This is a thin WRAPPER. The real air-gap payload already exists at
# warhacker/usb/ (DAY_OF_RUNBOOK.md, fallback/offline-deploy.sh, signed vessels
# Zarf, offline scenarios). This script locates the USB tree and hands off.
#
# Usage:
#   run.sh --usb /path/to/usb [--platform linux-amd64|darwin-arm64] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode C — air-gapped USB deploy (wrapper around warhacker/usb/).
  --usb PATH          (required) path to the USB payload root (warhacker/usb)
  --platform NAME     linux-amd64 (default) | darwin-arm64
  --dry-run
ENV that changes: PLATFORM, PATH (to USB bin/). See warhacker/usb/DAY_OF_RUNBOOK.md.
USAGE
}

USB=""
PLATFORM="linux-amd64"
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
log "Air-gap mode. The real payload lives at: ${USB}"
log "Reference runbook: ${USB}/DAY_OF_RUNBOOK.md (Paths A/B/C)."
export PLATFORM
export PATH="${USB}/bin/${PLATFORM}:${PATH}"
log "PLATFORM=${PLATFORM}; PATH now includes ${USB}/bin/${PLATFORM}"

log "1. Integrity first (in front of the room):"
if [ -x "${USB}/VERIFY.sh" ]; then
  run "${USB}/VERIFY.sh"
else
  warn "VERIFY.sh not found at USB root — run build_usb_payload.sh on T-1 (online) first."
fi

log "2. If the air-gapped cluster runs UDS Core, mesh vessels:"
log "   ${USB}/mesh_into_uds.sh"
log "   Else, stand up the pinned recovery k3d + vessels (fully offline):"
run "${USB}/fallback/offline-deploy.sh"

log "3. Run the governed-DENY + tamper scenarios (real crypto, fully offline):"
log "   cd ${USB}/scenarios && OFFLINE=true ./scenario_drone_loses_contact.sh && ./scenario_tamper_test.sh"

log "DONE — Mode C wrapper. All artifacts are pre-vendored on the stick. No internet used."
exit "${EC_OK}"
