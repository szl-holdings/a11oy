# sentra/doi-bind

**Operationalizes:** TH2 — Replay-Root → Mintable Zenodo Manifest  
**Repo:** szl-holdings/sentra  
**Path:** packages/doi-bind

## What it does

Converts a receipt chain (replay root) into a **Zenodo deposit manifest** (`deposit.json`) ready for DOI minting. The actual HTTP `POST` to Zenodo is intentionally **operator-gated** — this module only builds and validates the manifest; the mint step requires an explicit operator action.

### Manifest shape

The manifest follows the [Zenodo REST API v1](https://developers.zenodo.org/) deposit body schema:

- `metadata.upload_type = "dataset"`
- `metadata.related_identifiers` — one entry per receipt, using `sha256:<hash>` as identifier
- `sha256` — canonical SHA-256 of the sorted receipt hashes
- `pendingMint = true` — flag cleared only by the operator mint action

### Security

- No network calls in this module
- `pendingMint` defaults to `true`; callers must explicitly set it to `false` after a successful operator-approved mint

## Exports

| Symbol | Purpose |
|--------|---------|
| `buildManifest(chain, opts)` | Build manifest + `depositJson` |
| `computeChainHash(chain)` | SHA-256 of sorted receipt hashes |
| `ZenodoManifestSchema` | Zod schema for validation |

## Env vars

| Var | Purpose |
|-----|---------|
| `ZENODO_ACCESS_TOKEN` | Required only by the operator-gated mint step (not in this module) |

## HTTP endpoints

None — library only.

## Install & test

```bash
pnpm install
pnpm test
```
