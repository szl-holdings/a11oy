#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode G — DU hands over an OTel collector endpoint (their Tempo/Jaeger).
# Founder directive 2026-05-30 16:46 EDT.
#
# Sets OTEL_EXPORTER_OTLP_ENDPOINT on the receipts deployment and restarts.
# HONEST LIMIT: the receipts server only emits spans once PR#19's image is the
# running one (master has no OTLP env). The vessels Pepr side uses its own
# SZL_OTEL_ENDPOINT and can be set independently.
#
# Usage:
#   run.sh --otlp-endpoint http://collector.du:4317
#          [--namespace szl-receipts] [--deploy szl-receipts-server]
#          [--also-pepr --pepr-namespace NS --pepr-deploy NAME] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode G — OTel collector endpoint.
  --otlp-endpoint URL   (required) OTLP gRPC, e.g. http://tempo.du.svc:4317
  --namespace NS        (default: szl-receipts)
  --deploy NAME         (default: szl-receipts-server)
  --also-pepr           also set SZL_OTEL_ENDPOINT on the vessels Pepr deploy
  --pepr-namespace NS   (default: pepr-system)
  --pepr-deploy NAME    (default: pepr-szl-vessels-governance)
  --dry-run
ENV that changes (verified): OTEL_EXPORTER_OTLP_ENDPOINT (receipts, PR#19);
  SZL_OTEL_ENDPOINT (vessels Pepr).
USAGE
}

OTLP="" NS="szl-receipts" DEPLOY="szl-receipts-server"
ALSO_PEPR=false PEPR_NS="pepr-system" PEPR_DEPLOY="pepr-szl-vessels-governance"
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --otlp-endpoint) OTLP="${2:-}"; shift 2;;
    --namespace) NS="${2:-}"; shift 2;;
    --deploy) DEPLOY="${2:-}"; shift 2;;
    --also-pepr) ALSO_PEPR=true; shift;;
    --pepr-namespace) PEPR_NS="${2:-}"; shift 2;;
    --pepr-deploy) PEPR_DEPLOY="${2:-}"; shift 2;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done
[ -n "${OTLP}" ] || { err "--otlp-endpoint is required"; usage; exit "${EC_USAGE}"; }

fa001_banner
warn "Receipts-server OTLP export only works if PR#19's image is running. On a"
warn "stock master image there is no OTel SDK — do NOT claim live spans then."
need_cluster

log "1. Set OTEL_EXPORTER_OTLP_ENDPOINT on ${NS}/${DEPLOY}"
run kubectl -n "${NS}" set env "deploy/${DEPLOY}" "OTEL_EXPORTER_OTLP_ENDPOINT=${OTLP}"
run kubectl -n "${NS}" rollout restart "deploy/${DEPLOY}"
run kubectl -n "${NS}" rollout status "deploy/${DEPLOY}" --timeout=90s

if [ "${ALSO_PEPR}" = "true" ]; then
  log "2. Set SZL_OTEL_ENDPOINT on ${PEPR_NS}/${PEPR_DEPLOY}"
  run kubectl -n "${PEPR_NS}" set env "deploy/${PEPR_DEPLOY}" "SZL_OTEL_ENDPOINT=${OTLP}"
  run kubectl -n "${PEPR_NS}" rollout restart "deploy/${PEPR_DEPLOY}"
  run kubectl -n "${PEPR_NS}" rollout status "deploy/${PEPR_DEPLOY}" --timeout=90s
fi

log "DONE — Mode G. OTLP endpoint set to ${OTLP}."
exit "${EC_OK}"
