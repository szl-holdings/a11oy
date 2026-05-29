# A11oy Series-A diligence packet

A11oy is the operational hub for the SZL Holdings governed-AI substrate. The
investment-facing story is strongest when it is shown as a working control
plane, not a slide: GitHub checks, deterministic payloads, proof-aware doctrine
tests, and a Hugging Face mirror that points back to canonical provenance.

## What is real today

| Layer | Evidence |
| --- | --- |
| Doctrine runtime tests | `pnpm test:doctrine` runs nine core test files, including KS-18, LID, PAC-Bayes, quaternion, threshold, and composition checks. |
| Package typecheck/build | `pnpm typecheck:doctrine` and `pnpm build:doctrine` validate `@a11oy/core` and `@a11oy/connection`. |
| Payload integrity | `deploy/MANIFEST.json` and `pnpm payload:verify` provide per-file SHA-256 checks. |
| Operational bundle | `pnpm payload:bundle` emits a deterministic tarball plus `.sha256` sidecar. |
| Org-wide map | `docs/ecosystem-registry.json` tracks 19 visible public repos and their readiness tiers. |
| Thesis/proof alignment | `docs/PROVENANCE.md` pins v18 thesis DOI and Lean software DOI, and gates public claims by status. |
| GitHub validation | Doctrine Build, CodeQL, SBOM, Trivy, DCO, docs, links, and secret scan pass on the branch. |
| Hugging Face path | Manual workflow publishes the verified payload to `SZLHOLDINGS/a11oy-v19-substrate` when `HF_TOKEN` is available. |

## Investor framing

**A11oy is a governed execution fabric.** It sits between agentic actions and
enterprise consequences. Its job is not to be the model; its job is to make
model-driven actions accountable:

1. evaluate doctrine and policy constraints;
2. record receipts and provenance;
3. preserve a verifiable payload trail;
4. expose operator-ready artifacts for diligence and deployment.

## Differentiation

- **Proof-aware:** public claims point to thesis/proof/provenance records instead
  of unsupported marketing language.
- **Payload-native:** every deploy payload is manifestable and the operational
  bundle is reproducible from tracked source.
- **Org-spanning:** platform, thesis, Lean proofs, receipts, telemetry, trust,
  brand, and verticals are mapped in one registry.
- **Air-gap compatible:** Hugging Face is an explicit mirror/publish step; the
  shipped payload does not depend on outbound telemetry.

## Current roadmap gates

| Gate | Status |
| --- | --- |
| Merge operational GitHub branch | Ready after review. |
| Add `HF_TOKEN` as GitHub Actions secret | Required for live Hugging Face publish. |
| Run `Publish Hugging Face Payload` workflow | Publishes generated payload to Hugging Face. |
| Add UDS release artifact attestation parity | Next hardening pass. |
| Promote vertical scaffolds to implementation-backed surfaces | Product roadmap; tracked in ecosystem registry. |

## Verification command block

```bash
pnpm install
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
pnpm ecosystem:audit
pnpm payload:verify
pnpm payload:huggingface
pnpm payload:bundle
pnpm payload:bundle:verify
```

This packet is designed to be legible to engineers, security reviewers, and
capital allocators: it shows what runs, what is proven, what is packaged, and
what remains explicitly on the roadmap.
