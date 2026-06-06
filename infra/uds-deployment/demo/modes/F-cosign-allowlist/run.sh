#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode F — DU hands over a cosign SAN allowlist / pre-approved SANs.
# Founder directive 2026-05-30 16:46 EDT.
#
# Updates SZL_COSIGN_SAN_ALLOWLIST on the vessels Pepr Validate() deny path
# (vessels#81, MERGED) and restarts. Fail-closed: empty allowlist denies all.
#
# Usage:
#   run.sh --sans "san1,san2,..." [--oidc-issuer URL] [--enforce true|false]
#          [--pepr-namespace pepr-system] [--pepr-deploy NAME] [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode F — cosign SAN allowlist on the vessels Pepr deny path (vessels#81).
  --sans LIST           (required) comma-separated cert-identity SANs
                        e.g. https://github.com/szl-holdings/vessels/.github/workflows/*
  --oidc-issuer URL     (optional) sets SZL_COSIGN_OIDC_ISSUER
  --enforce true|false  (optional) SZL_VALIDATE_ENFORCE (default leaves as-is)
  --pepr-namespace NS   (default: pepr-system)
  --pepr-deploy NAME    (default: pepr-szl-vessels-governance)
  --dry-run
ENV that changes (verified in vessels pepr/governance-receipts.ts):
  SZL_COSIGN_SAN_ALLOWLIST, SZL_COSIGN_OIDC_ISSUER, SZL_VALIDATE_ENFORCE.
USAGE
}

SANS="" OIDC="" ENFORCE=""
PEPR_NS="pepr-system"
PEPR_DEPLOY="pepr-szl-vessels-governance"
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --sans) SANS="${2:-}"; shift 2;;
    --oidc-issuer) OIDC="${2:-}"; shift 2;;
    --enforce) ENFORCE="${2:-}"; shift 2;;
    --pepr-namespace) PEPR_NS="${2:-}"; shift 2;;
    --pepr-deploy) PEPR_DEPLOY="${2:-}"; shift 2;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done
[ -n "${SANS}" ] || { err "--sans is required (empty allowlist = deny everything, fail-closed)"; usage; exit "${EC_USAGE}"; }

need_cluster
ENVPAIRS=( "SZL_COSIGN_SAN_ALLOWLIST=${SANS}" )
[ -n "${OIDC}" ] && ENVPAIRS+=( "SZL_COSIGN_OIDC_ISSUER=${OIDC}" )
[ -n "${ENFORCE}" ] && ENVPAIRS+=( "SZL_VALIDATE_ENFORCE=${ENFORCE}" )

log "1. Set cosign allowlist env on ${PEPR_NS}/${PEPR_DEPLOY}"
run kubectl -n "${PEPR_NS}" set env "deploy/${PEPR_DEPLOY}" "${ENVPAIRS[@]}"
log "2. Restart Pepr controller"
run kubectl -n "${PEPR_NS}" rollout restart "deploy/${PEPR_DEPLOY}"
run kubectl -n "${PEPR_NS}" rollout status "deploy/${PEPR_DEPLOY}" --timeout=90s

log "DONE — Mode F. Validate() now admits images whose cosign SAN is in:"
log "   ${SANS}"
log "Demo beat: deploy an image signed by an allowed SAN -> ADMIT; unsigned/foreign SAN -> DENY (fail-closed)."
exit "${EC_OK}"
