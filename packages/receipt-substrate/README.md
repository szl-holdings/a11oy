# @szl-holdings/a11oy-receipt-substrate

Operational receipt chaining for MCP-style tool envelopes.

This package is the Lane A runtime slice for governed tool execution. It emits
canonical receipts for tool calls, links them into a hash chain, verifies local
payload and chain integrity, and can append receipts to JSONL files for UDS or
operator handoff.

## Run

```bash
npm test --prefix packages/receipt-substrate
npm run smoke --prefix packages/receipt-substrate
```

## CLI

```bash
node --experimental-strip-types packages/receipt-substrate/src/cli.ts   --out /tmp/a11oy-receipts.jsonl   --actor did:example:operator   --tool receipted_retrieval   --payload-json '{"query":"status","limit":3}'
```

The CLI reads the last receipt in the JSONL file, links the new receipt to it,
appends one line, then verifies the resulting chain.
