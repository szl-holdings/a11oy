#!/usr/bin/env bash
# Copyright 2026 SZL Holdings
# SPDX-License-Identifier: Apache-2.0
#
# Mode H — DU hands over a Kafka/NATS message bus. DOCUMENTATION ONLY.
# Founder directive 2026-05-30 16:46 EDT.
#
# There is NO live switch for this. Today receipts fan out via HTTP POST to
# szl-receipts-server (/v1/append). Swapping to a broker is a ~1-day refactor.
set -o errexit -o nounset -o pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "${HERE}/../../lib/common.sh"

DRY_RUN="${DRY_RUN:-false}"
case "${1:-}" in --dry-run) DRY_RUN=true;; esac

cat <<DOC
============================================================================
 Mode H — Kafka/NATS message bus  ::  DOCUMENTATION ONLY (no live switch)
============================================================================
 TODAY (real): the Pepr governance controller POSTs each receipt over HTTP to
   szl-receipts-server at path /v1/append (env SZL_RECEIPTS_URL on the Pepr
   deployment). The receipts server appends + chains them. This is the only
   fan-out that exists.

 TO SWAP to Kafka/NATS (NOT a Warhacker-day change):
   1. Add a producer in vessels pepr/governance-receipts.ts (publish receipt
      envelope to topic 'szl.receipts' instead of / in addition to HTTP POST).
   2. Add a consumer to szl-receipts-server (the service that ships in
      szl-uds-deployment#19, OPEN DRAFT) to ingest from the broker, preserving
      receipt-chain ordering + idempotency keys (chain prevHash dependency).
   3. New env (does NOT exist today): SZL_RECEIPTS_SINK=kafka|nats|http and a
      broker URL (e.g. SZL_KAFKA_BROKERS / SZL_NATS_URL).
   4. Handle exactly-once / at-least-once semantics for the hash chain.

 ESTIMATE: ~1 day of engineering. Do NOT pretend to publish to a broker on
 stage. If DU asks, say: "Today it's HTTP POST to the receipts server; a broker
 sink is a one-day refactor of szl-receipts-server (PR-stage at #19)."
============================================================================
DOC
[ "${DRY_RUN}" = "true" ] && log "dry-run acknowledged (mode is documentation only regardless)"
exit "${EC_NOTIMPL}"
