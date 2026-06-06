#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode D — DU hands over an OIDC issuer URL + client ID (Keycloak realm).
# Founder directive 2026-05-30 16:46 EDT.
#
# Honesty: the receipts SERVER signs with HMAC (no KEYCLOAK_ISSUER_URL baked
# into the pod). OIDC lives at the UDS gateway/authservice layer (Package CR
# spec.sso) and on the vessels Pepr cosign verifier (SZL_COSIGN_OIDC_ISSUER).
# This script updates the cosign OIDC issuer env on the running vessels Pepr
# deployment and prints the exact Package-CR sso fields to edit for the gateway.
#
# Usage:
#   run.sh --oidc-issuer-url URL --client-id ID [--audience AUD]
#          [--pepr-namespace pepr-system] [--pepr-deploy pepr-uds-core-watcher]
#          [--dry-run]
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

usage() {
  cat <<USAGE
Mode D — custom OIDC issuer + client ID.
  --oidc-issuer-url URL   (required) e.g. https://sso.du.mil/realms/dod
  --client-id ID          (required) Keycloak client id
  --audience AUD          (optional)
  --pepr-namespace NS     (default: pepr-system)
  --pepr-deploy NAME      (default: pepr-szl-vessels-governance)
  --dry-run
ENV that changes (verified): SZL_COSIGN_OIDC_ISSUER on the vessels Pepr deploy;
  spec.sso[].clientId in packages/{rosie,vessels}/uds-package.yaml + charts/szl-receipts.
USAGE
}

ISSUER="" CLIENT="" AUDIENCE=""
PEPR_NS="pepr-system"
PEPR_DEPLOY="pepr-szl-vessels-governance"
parse_common_flags "$@" || { usage; exit "${EC_USAGE}"; }
set -- "${PARSED_ARGS[@]:-}"
while [ "$#" -gt 0 ]; do
  case "${1:-}" in
    --oidc-issuer-url) ISSUER="${2:-}"; shift 2;;
    --client-id) CLIENT="${2:-}"; shift 2;;
    --audience) AUDIENCE="${2:-}"; shift 2;;
    --pepr-namespace) PEPR_NS="${2:-}"; shift 2;;
    --pepr-deploy) PEPR_DEPLOY="${2:-}"; shift 2;;
    "") shift;;
    *) err "unknown arg: $1"; usage; exit "${EC_USAGE}";;
  esac
done
[ -n "${ISSUER}" ] || { err "--oidc-issuer-url is required"; usage; exit "${EC_USAGE}"; }
[ -n "${CLIENT}" ] || { err "--client-id is required"; usage; exit "${EC_USAGE}"; }
case "${ISSUER}" in https://*) ;; *) die "OIDC issuer must be https:// — got: ${ISSUER}" "${EC_USAGE}";; esac

need_cluster
log "1. Update the vessels Pepr cosign OIDC issuer (SZL_COSIGN_OIDC_ISSUER)"
run kubectl -n "${PEPR_NS}" set env "deploy/${PEPR_DEPLOY}" "SZL_COSIGN_OIDC_ISSUER=${ISSUER}"
log "2. Restart the Pepr controller to pick up the new issuer"
run kubectl -n "${PEPR_NS}" rollout restart "deploy/${PEPR_DEPLOY}"
run kubectl -n "${PEPR_NS}" rollout status "deploy/${PEPR_DEPLOY}" --timeout=90s

cat <<NEXT
  ----------------------------------------------------------------------------
  GATEWAY / HUMAN-LOGIN (edit Package CRs, then re-apply via UDS):
    packages/rosie/uds-package.yaml      -> spec.sso[0].clientId: ${CLIENT}
    packages/vessels/uds-package.yaml    -> spec.sso[0].clientId (operator view)
    charts/szl-receipts/templates/uds-package.yaml -> spec.sso[0].clientId
    Issuer realm comes from DU UDS Core's Keycloak; redirectUris must include
    the tenant gateway host. Audience (${AUDIENCE:-<none>}) -> sso scopes.
  HONEST LIMIT: there is no standalone human login to demo unless a module image
  is deployed behind the gateway (FA-001). This mode wires the cosign verifier
  issuer for real; the SSO login is a config story until images exist.
  ----------------------------------------------------------------------------
NEXT
log "DONE — Mode D. Cosign OIDC issuer updated; gateway SSO fields printed above."
exit "${EC_OK}"
