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

## Two-witness research evidence v0

The offline comparison core normalizes OpenAI Responses web-search evidence and
Perplexity Search evidence into one deterministic source shape. It binds the
query and policy SHA-256 digests, provider/API surface, response ID, status,
HTTP status, caller-observed latency, usage, provider-reported cost when
available, sanitized source metadata, and source-list digest into the existing
operational receipt chain.

The comparison emits only:

- `CORROBORATED` when both successful providers share at least one canonical
  source URL;
- `DIVERGENT` when both successful providers return non-empty, disjoint source
  URL sets;
- `SINGLE_PROVIDER` when exactly one provider supplies evidence;
- `INSUFFICIENT` for empty evidence or any digest/source-list integrity error;
- `UNAVAILABLE` when neither provider succeeds.

These labels do not authorize an action. The receipt explicitly records
`evidence_class: MODELED`, `signature_state: UNSIGNED_LOCAL`,
`external_attestation_state: EXTERNAL_ATTESTATION_FALSE`, and
`action_authorization_state: ACTION_AUTHORIZED_FALSE` alongside the matching
false boolean fields.

Live provider adapters are feature-flagged off. This package accepts no
provider credentials, performs no network calls, excludes raw queries and
snippets, and strips common credential and tracking parameters from source
URLs. Network-free fixtures exercise matching, disjoint, one-provider-down,
empty, query/policy digest mismatch, tampered source-list, and unavailable
states.

Provider shape references:

- [OpenAI Responses API web search](https://platform.openai.com/docs/guides/tools-web-search)
- [Perplexity Search API](https://docs.perplexity.ai/api-reference/search-post)
