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
| Demo readiness report | `docs/ecosystem-readiness-report.json` classifies active, supporting, excluded, and upstream-fix-needed repos. |
| Thesis/proof alignment | `docs/PROVENANCE.md` pins v18 thesis DOI and Lean software DOI, and gates public claims by status. |
| Market evidence map | `docs/SERIES_A_MARKET_EVIDENCE.md` maps NIST AI RMF, EU AI Act, CISA SBOM, SLSA, and model-card expectations to A11oy artifacts and gaps. |
| GitHub validation | Doctrine Build, CodeQL, SBOM, Trivy, DCO, docs, links, and secret scan pass on the branch. |
| Hugging Face path | Manual workflow publishes the verified payload to `SZLHOLDINGS/a11oy-v19-substrate` when `HF_TOKEN` is available. |
| UDS / Warhacker proof point | `docs/WARHACKER_UDS_PROOF_POINT.md` ties the package, manifest, attestation, receipt-chain, and tamper-test demo together. |
| Live correction evidence | `huggingface/DEMO_RECEIPT_SAMPLE.jsonl` records the current blocked claims: inflated Putnam discharge, unmerged gate totals, and unsigned/empty v0.3.x release language. |

## Investor framing

**A11oy is a governed execution fabric.** It sits between agentic actions and
enterprise consequences. Its job is not to be the model; its job is to make
model-driven actions accountable:

1. evaluate doctrine and policy constraints;
2. record receipts and provenance;
3. preserve a verifiable payload trail;
4. expose operator-ready artifacts for diligence and deployment.

The market reason this matters is external, not invented: AI risk frameworks,
high-risk AI regulation, SBOM guidance, SLSA provenance, and model-card practice
all point toward traceability, documentation, oversight, and reproducible
evidence. A11oy turns those requirements into a demoable GitHub/HF packet rather
than a slide.

## Differentiation

- **Proof-aware:** public claims point to thesis/proof/provenance records instead
  of unsupported marketing language.
- **Payload-native:** every deploy payload is manifestable and the operational
  bundle is reproducible from tracked source.
- **Org-spanning:** platform, thesis, Lean proofs, receipts, telemetry, trust,
  brand, and verticals are mapped in one registry.
- **Air-gap compatible:** Hugging Face is an explicit mirror/publish step; the
  shipped payload does not depend on outbound telemetry.
- **UDS/Zarf-aware:** A11oy has an operator proof-point lane for package
  inspection, manifest verification, attestation review, and receipt-chain
  smoke testing.

## Active showcase scope

The Series-A showcase centers the public repos with implementation or
supporting evidence: `a11oy`, `amaru`, `sentra`, `rosie`, `ouroboros`,
`lutar-lean`, `ouroboros-thesis`, `uds-mesh`, `vsp-otel`, `vessels`,
`agi-forecast`, `szl-trust`, `szl-brand`, `szl-cookbook`, `.github`, and
`platform`.

`counsel`, `terra`, and `carlota-jo` are intentionally excluded from active-demo
claims until funded. The showcase also avoids stale product-name framing such
as `KORA`, `LUMINA`, `PARAGON`, or active `Lyte` copy.

## Current roadmap gates

| Gate | Status |
| --- | --- |
| Merge operational GitHub branch | Ready after review. |
| Add `HF_TOKEN` as GitHub Actions secret | Required for live Hugging Face publish. |
| Run `Publish Hugging Face Payload` workflow | Publishes generated payload to Hugging Face. |
| Add UDS release artifact attestation parity | Next hardening pass. |
| Repair upstream proof/release caveats | `lutar-lean` latest proof CI and `ouroboros-thesis` v18 release reconciliation should be fixed before broad all-green proof language. |
| Promote excluded vertical scaffolds to implementation-backed surfaces | Funding roadmap; tracked in ecosystem registry. |

## Current correction ledger

| Area | Investor-safe wording |
| --- | --- |
| Putnam | `1/12` is the current truly discharged Lean posture; additional claims require a current upstream proof report. |
| Runtime gates | A11oy main can cite seven policy gate files and ten theorem-runtime manifest entries. G36-G40 and broader totals are not live until merged and validated. |
| UDS v0.3.0 | A11oy v0.3.0 has SBOM assets only; Vessels v0.3.0 has zero release assets. Use earlier signed assets or future owner-pushed assets for signed payload proof. |
| GHCR | Treat GHCR package availability as founder/owner release work until package push and visibility are confirmed. |

## Verification command block

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
```

This packet is designed to be legible to engineers, security reviewers, and
capital allocators: it shows what runs, what is proven, what is packaged, and
what remains explicitly on the roadmap.
