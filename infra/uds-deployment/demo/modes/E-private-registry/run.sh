#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode E — DU hands over a private OCI registry behind their firewall.
# Founder directive 2026-05-30 16:46 EDT.
#
# Mirror our images into DU's registry (zarf tools registry copy / crane copy),
# then re-deploy with rewritten image refs.
#
# HONEST LIMIT (FA-001): only vessels has a real image to mirror today. The
# four staged modules have NO source image to copy.
#
# Usage:
#   run.sh --registry du-registry.internal:5000 [--namespace szl] [--crane] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode E — private OCI registry mirror + re-deploy.
  --registry HOST[:PORT]   (required) DU's registry (e.g. registry.du.mil:5000)
  --namespace NS           (default: szl-receipts)
  --crane                  use crane copy instead of zarf tools registry copy
  --dry-run
ENV/config that changes: ZARF_REGISTRY_URL / --registry-url on zarf init;
  helm --set server.image.repository=<registry>/szl-holdings/szl-receipts-server.
USAGE
}

REGISTRY="" NAMESPACE="szl-receipts" USE_CRANE=false
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --registry) REGISTRY="${2:-}"; shift 2;;
    --namespace) NAMESPACE="${2:-}"; shift 2;;
    --crane) USE_CRANE=true; shift;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done
[ -n "${REGISTRY}" ] || { err "--registry is required"; usage; exit "${EC_USAGE}"; }

fa001_banner
SRC_RECEIPTS="ghcr.io/szl-holdings/szl-receipts-server:uds-v0.3.1"   # PR#19 ref
DST_RECEIPTS="${REGISTRY}/szl-holdings/szl-receipts-server:uds-v0.3.1"

log "1. Mirror images into ${REGISTRY}"
warn "FA-001: only vessels' image exists. szl-receipts-server image ships in PR#19 (DRAFT) — confirm it's built before relying on this."
if [ "${USE_CRANE}" = "true" ]; then
  need_cmd crane
  run crane copy "${SRC_RECEIPTS}" "${DST_RECEIPTS}"
else
  need_cmd zarf
  run zarf tools registry copy "${SRC_RECEIPTS}" "${DST_RECEIPTS}"
fi
log "   (For the vessels signed Zarf package, prefer: zarf package deploy with"
log "    --registry-url ${REGISTRY} so Zarf pushes its bundled images for you.)"

log "2. Re-deploy szl-receipts with the rewritten image ref"
REPO_ROOT="$(demo_repo_root)"
run helm upgrade --install szl-receipts "${REPO_ROOT}/charts/szl-receipts" \
    --namespace "${NAMESPACE}" --create-namespace \
    --set "server.image.repository=${REGISTRY}/szl-holdings/szl-receipts-server" \
    --set "server.image.tag=uds-v0.3.1"

log "3. For Zarf init on the DU cluster (one-time):"
log "   zarf init --registry-url ${REGISTRY} --confirm   # or set ZARF_REGISTRY_URL"

log "DONE — Mode E. Images mirrored to ${REGISTRY}; receipts re-deployed against it."
exit "${EC_OK}"
