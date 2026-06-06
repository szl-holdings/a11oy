#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode I — DU asks for IL5+/FedRAMP-aligned crypto. DOCUMENTATION ONLY.
# Founder directive 2026-05-30 16:46 EDT.
#
# Cross-references docs/KEY_CUSTODY_RUNBOOK.md (szl-uds-deployment#21).
# This is a 6-8 week compliance effort, not a Warhacker-day switch.
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

DRY_RUN="${DRY_RUN:-false}"
case "${1:-}" in --dry-run) DRY_RUN=true;; esac

cat <<DOC
============================================================================
 Mode I — IL5+/FedRAMP crypto (HSM/FIPS)  ::  DOCUMENTATION ONLY
============================================================================
 TODAY (honest): receipts are signed with HMAC-SHA-256 on master; Ed25519
   software key in a k8s Secret is PR-stage (szl-uds-deployment#19). Per the
   key-custody runbook this is Tier 0. The code itself self-labels "HSM-in-prod"
   as documentation-only — there is NO HSM and NO FIPS evidence today.

 TO REACH DoD-deployable (Tier 2, per docs/KEY_CUSTODY_RUNBOOK.md, PR#21):
   - External KMS / HSM. Reference option: AWS CloudHSM hsm2m.medium,
     FIPS 140-3 Level 3, Certificate #4703. Key generated + used inside the HSM
     via PKCS#11; the signer calls the HSM, the private key never leaves it.
   - Add a PKCS#11-backed signer to szl-receipts-server (new backend, env e.g.
     SZL_SIGNER_BACKEND=cloudhsm + PKCS#11 lib/slot config) — does NOT exist.
   - Produce FIPS 140-3 evidence + attestation + the ATO paperwork trail.
   - Networking: HSM ENI reachability, mTLS (Istio PeerAuthentication STRICT).

 ESTIMATE: 6-8 weeks of compliance + engineering. NOT a demo-day switch.
 On stage, never claim FIPS/IL5. Say: "Tier 0 today; the runbook maps the
 Tier 2 HSM migration — that's a procurement-stage effort, not a config flip."
============================================================================
DOC
[ "${DRY_RUN}" = "true" ] && log "dry-run acknowledged (mode is documentation only regardless)"
exit "${EC_NOTIMPL}"
