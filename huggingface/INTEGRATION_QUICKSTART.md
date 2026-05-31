# Integration quickstart — current A11oy surface

This quickstart uses the repository surfaces that exist today. It does not
advertise a Python package, an LLM wrapper, or a hosted model endpoint.

## 1. Clone and install

```bash
git clone https://github.com/szl-holdings/a11oy.git
cd a11oy
pnpm install
```

## 2. Verify doctrine packages

```bash
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
```

## 3. Verify the operational receipt substrate

```bash
npm test --prefix packages/receipt-substrate
npm run smoke --prefix packages/receipt-substrate
npm run selftest --prefix packages/receipt-substrate
```

The smoke command appends a local JSONL receipt and verifies the resulting hash
chain. The selftest command runs the same path against an ephemeral temp file
(emit, append, read back, verify, plus a tampered-chain negative control) and
exits non-zero if the bundled substrate is not functional — it is also wired
into the container entrypoint as `a11oy selftest`.

## 4. Verify deploy payload integrity

```bash
pnpm payload:verify
```

This checks `deploy/MANIFEST.json` against the files under `deploy/`.

## 5. Generate the Hugging Face diligence mirror

```bash
pnpm ecosystem:readiness
pnpm payload:huggingface
```

The generated folder is `dist/huggingface/a11oy/`.

## 6. Build the operational review bundle

```bash
pnpm payload:bundle
pnpm payload:bundle:verify
```

The bundle contains the generated Hugging Face packet, deploy manifests,
selected source docs, scripts, and built doctrine outputs.

## 7. UDS/Zarf operator path

Use the GitHub docs as the canonical operator source:

- `artifacts/a11oy-uds/README.md`
- `artifacts/a11oy-uds/docs/OPERATOR-QUICKSTART.md`
- `docs/WARHACKER_UDS_PROOF_POINT.md`

If Zarf is unavailable, the documented fallback is a development verification
mode only. Do not present fallback tarballs as deployable Zarf packages.

