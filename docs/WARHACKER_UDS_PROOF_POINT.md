# Warhacker UDS proof point

This is the Defense-Unicorns-facing shape for the A11oy demo. It connects the
existing governed-execution substrate to UDS/Zarf without implying endorsement,
catalog acceptance, or partnership.

## Objective

Show a running, inspectable proof point for trusted AI/agent orchestration in a
UDS-style operator workflow:

- payload artifacts are content-addressed;
- operator actions emit verifiable receipts;
- package metadata can be inspected before deploy;
- public claims route back to GitHub evidence.

## Option A — three-week proof point

| Week | Deliverable | Evidence |
| --- | --- | --- |
| 1 | Build/verify A11oy UDS payload from source | `artifacts/a11oy-uds/scripts/build.sh`, `deploy/MANIFEST.json` |
| 2 | Receipt-chain demo with tamper failure | `packages/receipt-substrate`, `npm test --prefix packages/receipt-substrate` |
| 3 | Operator walkthrough packet | Hugging Face mirror + GitHub release/check links + short demo video |

## Demo script

```bash
# 1. Validate runtime receipt primitives.
npm test --prefix packages/receipt-substrate
npm run smoke --prefix packages/receipt-substrate

# 2. Validate doctrine package lane.
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine

# 3. Validate deploy payload integrity.
pnpm payload:verify

# 4. Generate the public diligence mirror.
pnpm payload:huggingface

# 5. Build and verify the operational review tarball.
pnpm payload:bundle
pnpm payload:bundle:verify
```

## UDS/Zarf inspection lane

Where Zarf is available, the proof point should add:

```bash
zarf package inspect a11oy-uds-<version>.tar.zst
zarf package deploy a11oy-uds-<version>.tar.zst --confirm
```

Where Zarf is not available, use the documented source fallback only as a CI/dev
verification mode. The fallback tarball is not a deployable Zarf package and
must not be presented as one.

## Tamper test

1. Unpack a generated payload.
2. Modify any file listed in `MANIFEST.json`.
3. Re-run manifest verification.
4. Show the verifier failing on the changed SHA-256.

That failure is the point: the operator can trust the package because mutation
breaks the manifest trail.

## What to say

Use:

- “UDS/Zarf-compatible proof point.”
- “Operator handoff with manifest and attestation verification.”
- “A11oy is the governed-execution fabric; UDS is the delivery/control-plane
  context we are integrating with.”

Avoid:

- “Defense Unicorns endorsed.”
- “Accepted into the UDS catalog.”
- “Deploys to every UDS environment.”
- “All formal proof work is green.”

## Evidence bundle checklist

- GitHub branch/PR URL.
- A11oy release URL.
- UDS release URL (`uds-v0.2.0` or newer).
- Workflow run URLs for Doctrine Build, Operational Validation, SBOM, CodeQL.
- `MANIFEST.json` and attestation excerpts.
- Receipt JSONL sample and verifier output.
- Hugging Face mirror URL.

