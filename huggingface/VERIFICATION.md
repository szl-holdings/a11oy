# Verification guide

Run these commands from the canonical GitHub checkout:

```bash
pnpm install
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
pnpm ecosystem:audit
pnpm ecosystem:readiness
pnpm payload:verify
pnpm payload:huggingface
pnpm payload:bundle
pnpm payload:bundle:verify
npm test --prefix packages/receipt-substrate
```

## What each command proves

| Command | Evidence |
| --- | --- |
| `pnpm test:doctrine` | Core A11oy runtime/governance tests execute. |
| `pnpm typecheck:doctrine` | Doctrine packages typecheck. |
| `pnpm build:doctrine` | Doctrine packages emit build artifacts. |
| `pnpm ecosystem:audit` | The curated public repo registry is structurally valid. |
| `pnpm ecosystem:readiness` | The checked-in readiness report matches the generator. |
| `pnpm payload:verify` | Deploy manifest SHA-256 entries match tracked payload files. |
| `pnpm payload:huggingface` | This Hugging Face packet is regenerated from source. |
| `pnpm payload:bundle` | Operational review tarball is built from tracked source and outputs. |
| `pnpm payload:bundle:verify` | Operational tarball checksum and required files verify. |
| `npm test --prefix packages/receipt-substrate` | Operational receipt chain, quorum, tamper, and replay checks pass. |

## Demo receipt sample

`DEMO_RECEIPT_SAMPLE.jsonl` uses the current
`packages/receipt-substrate/src/index.ts` shape. It contains four synthetic
investor-demo receipts:

1. evidence retrieval for Vessels UDS signed-asset status;
2. policy blocking an unsupported signed-asset claim;
3. unsupported-claim guard correcting inflated Putnam and gate-count language;
4. chain verification summary that points back to the receipt-substrate test.

## Tamper check

To demonstrate why the manifest matters:

1. Generate or unpack a payload.
2. Modify any file listed in `payloads/deploy/MANIFEST.json`.
3. Re-run the manifest verifier from GitHub.
4. The verifier should fail because the file bytes no longer match the recorded
   SHA-256.

## Canonical sources

- GitHub: <https://github.com/szl-holdings/a11oy>
- A11oy release: <https://github.com/szl-holdings/a11oy/releases/tag/v1.0.1>
- UDS payload release line: <https://github.com/szl-holdings/a11oy/releases/tag/uds-v0.2.0>
- Thesis DOI: <https://doi.org/10.5281/zenodo.20434276>
- Lean proof software DOI: <https://doi.org/10.5281/zenodo.20434308>

