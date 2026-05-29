#!/usr/bin/env bash
# validate-operational.sh — local/CI gate for the real operational surfaces.
#
# This script intentionally validates the runtime surfaces that are not covered
# by docs-only CI: operational receipts, UDS manifest generation, and UDS
# attestation verification. It does not require network access or package
# installation in the minimal cloud-agent image.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECEIPT_JSONL="${RECEIPT_JSONL:-/tmp/a11oy-operational-receipts.jsonl}"

log() { printf '[validate-operational] %s
' "$*"; }

cd "${REPO_ROOT}"

log "syntax-check shell entrypoints"
bash -n scripts/clone-org-repos.sh
bash -n scripts/release/lib/stage-v2-packages.sh
bash -n artifacts/a11oy-uds/scripts/build.sh

log "receipt substrate unit tests"
npm test --prefix packages/receipt-substrate

log "receipt substrate CLI smoke"
rm -f "${RECEIPT_JSONL}"
npm run smoke --prefix packages/receipt-substrate
node --experimental-strip-types packages/receipt-substrate/src/cli.ts   --out "${RECEIPT_JSONL}"   --actor did:example:operator   --tool receipted_retrieval   --payload-json '{"query":"followup","limit":1}'
node --input-type=module -e "import { readFileSync } from 'node:fs'; const lines = readFileSync(process.env.RECEIPT_JSONL || '${RECEIPT_JSONL}', 'utf8').trim().split(/\n/); if (lines.length !== 2) throw new Error('expected 2 receipt JSONL lines, got ' + lines.length); console.log('[validate-operational] receipt JSONL lines=' + lines.length);"

log "UDS fallback build with manifest + attestations"
A11OY_UDS_ALLOW_SOURCE_FALLBACK=1 bash artifacts/a11oy-uds/scripts/build.sh

log "verify UDS manifest"
node artifacts/a11oy-uds/scripts/verify-manifest.mjs artifacts/a11oy-uds/build

log "verify UDS attestations"
node artifacts/a11oy-uds/scripts/verify-attestations.mjs   artifacts/a11oy-uds/build   artifacts/a11oy-uds/build-attestations

log "OK"
