# Operational receipt substrate

`packages/receipt-substrate` is the operational Lane A receipt layer for
MCP-style tool calls, Cursor agent edits, Claude subagent calls, and internal
A11oy operations.

It turns a canonical tool envelope into an `OperationalReceipt`, links receipts
with `prev_receipt_hash`, verifies payload and Merkle-root consistency, checks
quorum signatures against configured nodes, and can append receipts to JSONL for
operator handoff or UDS packaging.

## Why this exists

The org already has policy receipts (`packages/policy`) and QEC lineage
primitives (`packages/qec-integrity`). The receipt substrate fills the runtime
handoff between agent/tool execution and those integrity surfaces:

```mermaid
flowchart LR
  Tool[MCP / Cursor / Claude operation] --> Env[ToolEnvelope]
  Env --> Rec[OperationalReceipt]
  Rec --> Chain[Hash-chain verification]
  Chain --> Jsonl[JSONL receipt ledger]
  Jsonl --> UDS[UDS / operator handoff]
```

## Run tests

```bash
npm test --prefix packages/receipt-substrate
```

## Emit an operational receipt

```bash
node --experimental-strip-types packages/receipt-substrate/src/cli.ts   --out /tmp/a11oy-receipts.jsonl   --actor did:example:operator   --tool receipted_retrieval   --payload-json '{"query":"status","limit":3}'
```

The CLI reads the existing JSONL file if present, links the new receipt to the
last receipt, verifies the next chain, appends one canonical JSON line, and
prints the receipt id, Merkle root, and sequence.

## Controls implemented

- Deterministic canonical JSON with sorted object keys and NFC string
  normalization.
- SHA3-256 hashing when Node exposes it, with SHA-256 fallback for runtimes that
  do not expose SHA3.
- TAI64N-style monotonic timestamp field plus ISO-8601 timestamp.
- Payload hash verification from the stored envelope.
- Merkle-root verification from the receipt body.
- Duplicate receipt-id, chain-link, timestamp-regression, and quorum checks.
- QEC witness fields for Shor repetition and CSS parity consistency.

## Non-goals

- This package does not replace `packages/policy`; policy YAML validation stays
  there.
- This package does not modify `web/packages/a11oy-core`; doctrine math remains
  a separate Lane B surface.
- This package does not claim external attestation. JSONL output is a local
  ledger input for downstream signing, UDS packaging, or external witness
  services.

## UDS package handoff

The Replit/platform UDS payload now lives in `artifacts/a11oy-uds/`. To stage
the payload, write `MANIFEST.json`, write `ATTESTATIONS.json`, verify both, and
produce a local fallback archive in environments without Zarf, run:

```bash
A11OY_UDS_ALLOW_SOURCE_FALLBACK=1 bash artifacts/a11oy-uds/scripts/build.sh
```

Release builds should run without `A11OY_UDS_ALLOW_SOURCE_FALLBACK`, after
installing workspace dependencies and Zarf. The fallback archive is intentionally
written under `dist/a11oy-uds-fallback/` and is not a deployable Zarf package.
