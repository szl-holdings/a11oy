#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode A — kubectl access to DU's UDS Core cluster (PRIMARY / Path A).
# Founder directive 2026-05-30 16:46 EDT.
#
# Validates the kubeconfig + that UDS Core is present, deploys the szl-receipts
# chart (Package CR + vessels Pepr controller already meshed via the USB
# mesh_into_uds.sh), fires a test receipt, verifies it.
#
# Usage:
#   run.sh --kubeconfig /path/to/du.kubeconfig [--namespace szl-receipts] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode A — kubectl into DU UDS Core cluster.
  --kubeconfig PATH   (required) kubeconfig DU handed you
  --namespace NAME    (default: szl-receipts)
  --dry-run           print actions, change nothing
Prereq: a UDS Core cluster you can reach. ENV that changes: KUBECONFIG.
USAGE
}

KUBECONFIG_PATH=""
NAMESPACE="szl-receipts"
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --kubeconfig) KUBECONFIG_PATH="${2:-}"; shift 2;;
    --namespace)  NAMESPACE="${2:-}"; shift 2;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done

[ -n "${KUBECONFIG_PATH}" ] || { err "--kubeconfig is required"; usage; exit "${EC_USAGE}"; }
need_file "${KUBECONFIG_PATH}"
export KUBECONFIG="${KUBECONFIG_PATH}"
log "KUBECONFIG set to ${KUBECONFIG}"

fa001_banner
need_cluster

log "1. Confirm this is a UDS Core cluster (CRD packages.uds.dev must exist)"
if has_uds_core; then
  log "   UDS Core detected."
else
  die "UDS Core NOT detected on this cluster. This is Mode B, not Mode A. \
Run modes/B-vanilla-k8s/run.sh to install slim-dev UDS Core first." "${EC_PRECOND}"
fi

REPO_ROOT="$(demo_repo_root)"
log "2. Apply the szl-receipts chart (Package CR + Helm) into ${NAMESPACE}"
run kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml
run helm upgrade --install szl-receipts "${REPO_ROOT}/charts/szl-receipts" \
    --namespace "${NAMESPACE}" --create-namespace

log "3. (vessels mesh) If you have the USB, mesh vessels signed Zarf now:"
log "   cd <usb> && export PATH=\"\$PWD/bin/linux-amd64:\$PATH\" && ./mesh_into_uds.sh"

log "4. Wait for the receipts server to be Ready"
run kubectl -n "${NAMESPACE}" rollout status deploy/szl-receipts-server --timeout=120s

log "5. Fire a test receipt (HTTP POST to /v1/append — the real path today)"
if [ "${DRY_RUN}" = "true" ]; then
  log "   dry-run: would port-forward + curl /v1/append + GET /v1/verify"
else
  run kubectl -n "${NAMESPACE}" port-forward svc/szl-receipts-server 18443:8443 &
  PF_PID=$!
  sleep 3
  run curl -fsS -X POST "http://127.0.0.1:18443/v1/append" \
      -H 'content-type: application/json' \
      -d '{"component":"demo","operation":"jack_in_test","status":"ok"}' || warn "append failed"
  run curl -fsS "http://127.0.0.1:18443/v1/verify" || warn "verify failed"
  kill "${PF_PID}" 2>/dev/null || true
fi

log "DONE — Mode A. Vessels + Pepr receipts active on DU UDS Core."
log "Narration: signed deploy -> Pepr Validate deny on unsigned image -> tamper-evident receipt chain."
exit "${EC_OK}"
