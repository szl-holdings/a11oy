#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode B — vanilla k8s/k3d cluster WITHOUT UDS Core.
# Founder directive 2026-05-30 16:46 EDT.
#
# Two sub-paths:
#   (default) install UDS Core slim-dev profile, then chain into Mode A.
#   --no-uds-core: deploy szl-receipts via the k3s kustomize overlay (PR#19),
#                  without the mesh/gateway story.
#
# TIME COST: UDS Core slim-dev takes ~10-15 min to come up. Budget for it.
#
# Usage:
#   run.sh --kubeconfig PATH [--no-uds-core] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode B — vanilla k8s/k3d (no UDS Core).
  --kubeconfig PATH   (required)
  --no-uds-core       skip UDS Core; deploy via kustomize k3s overlay (PR#19)
  --dry-run
PREREQ NOTE: default path installs UDS Core slim-dev (~10-15 min), then runs Mode A.
USAGE
}

KUBECONFIG_PATH=""
NO_UDS=false
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --kubeconfig) KUBECONFIG_PATH="${2:-}"; shift 2;;
    --no-uds-core) NO_UDS=true; shift;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done
[ -n "${KUBECONFIG_PATH}" ] || { err "--kubeconfig is required"; usage; exit "${EC_USAGE}"; }
need_file "${KUBECONFIG_PATH}"
export KUBECONFIG="${KUBECONFIG_PATH}"
fa001_banner
need_cluster

if has_uds_core; then
  warn "UDS Core already present — this is really Mode A. Chaining to Mode A."
  exec "${HERE}/../A-uds-core-kubectl/run.sh" --kubeconfig "${KUBECONFIG_PATH}" \
       $([ "${DRY_RUN}" = "true" ] && echo --dry-run)
fi

REPO_ROOT="$(demo_repo_root)"

if [ "${NO_UDS}" = "true" ]; then
  log "Path B2: NO UDS Core. Deploy szl-receipts via kustomize k3s overlay (PR#19)."
  OVERLAY="${REPO_ROOT}/kustomize/overlays/k3s"
  if [ ! -d "${OVERLAY}" ]; then
    die "kustomize overlay not found at ${OVERLAY}. It ships in szl-uds-deployment#19 \
(OPEN DRAFT). Merge/cherry-pick PR#19 or use the default UDS Core path." "${EC_PRECOND}"
  fi
  run kubectl apply -k "${OVERLAY}"
  run kubectl rollout status deploy/szl-receipts-server -n szl-receipts --timeout=120s
  warn "No mesh/gateway/authservice story in this sub-path (no UDS Core)."
  log "DONE — Mode B (no UDS Core). Receipts running standalone."
  exit "${EC_OK}"
fi

log "Path B1: install UDS Core slim-dev (~10-15 min), then run Mode A."
need_cmd uds
log "   This downloads UDS Core; requires internet or a warm cache (T-1)."
run uds deploy k3d-core-slim-dev:0.* --confirm
log "Waiting for UDS Core operator (packages.uds.dev CRD) ..."
if [ "${DRY_RUN}" != "true" ]; then
  for i in $(seq 1 60); do
    if kubectl get crd packages.uds.dev >/dev/null 2>&1; then break; fi
    sleep 15
  done
  has_uds_core || die "UDS Core did not come up in time" "${EC_CLUSTER}"
fi
log "UDS Core up. Chaining to Mode A."
exec "${HERE}/../A-uds-core-kubectl/run.sh" --kubeconfig "${KUBECONFIG_PATH}" \
     $([ "${DRY_RUN}" = "true" ] && echo --dry-run)
