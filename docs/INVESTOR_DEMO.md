# A11oy investor demo packet

This is the five-minute path through the SZL Holdings governed-AI substrate.
It is written for investors, technical diligence reviewers, and UDS operators
who need to see what is real, what runs, what is packaged, and what remains
explicitly out of active-demo scope.

## Start here

| Step | What to open | What it proves |
| --- | --- | --- |
| 1 | [`README.md`](../README.md) | A11oy is the operational hub, not an LLM checkpoint. |
| 2 | [`docs/PROVENANCE.md`](PROVENANCE.md) | Public claims are status-gated before they reach GitHub or Hugging Face. |
| 3 | [`docs/ecosystem-readiness-report.json`](ecosystem-readiness-report.json) | Every visible SZL repo is classified by demo readiness and evidence. |
| 4 | [`artifacts/a11oy-uds/README.md`](../artifacts/a11oy-uds/README.md) | A11oy has a UDS/Zarf payload lane with manifests and attestation checks. |
| 5 | [`packages/receipt-substrate`](../packages/receipt-substrate) | Tool-envelope receipts can be emitted, chained, and verified locally. |
| 6 | [`deploy/MANIFEST.json`](../deploy/MANIFEST.json) | Deploy payload files are content-addressed with SHA-256. |
| 7 | [`huggingface/README.md`](../huggingface/README.md) | Hugging Face is a generated diligence mirror tied back to GitHub. |
| 8 | [`docs/UDS_FRONTIER_GAP_MAP.md`](UDS_FRONTIER_GAP_MAP.md) | UDS/Zarf fit and gaps are mapped against public Defense Unicorns docs. |

## One-line thesis

A11oy turns agentic work into governed execution: every consequential action is
policy-checked, receipt-backed, payload-manifested, and traceable to a public
provenance contract.

## What is demo-ready now

| Surface | Demo status | Evidence |
| --- | --- | --- |
| A11oy doctrine package lane | Demo-ready | `pnpm test:doctrine`, `pnpm typecheck:doctrine`, `pnpm build:doctrine` |
| Operational receipt chain | Demo-ready | `npm test --prefix packages/receipt-substrate` and `npm run smoke --prefix packages/receipt-substrate` |
| Deploy manifest verification | Demo-ready | `pnpm payload:verify` |
| Hugging Face payload generation | Demo-ready | `pnpm payload:huggingface` |
| Operational tarball bundle | Demo-ready | `pnpm payload:bundle` and `pnpm payload:bundle:verify` |
| UDS/Zarf handoff | Demo-ready as package/operator proof point | `artifacts/a11oy-uds/README.md`, `artifacts/a11oy-uds/docs/*`, `deploy/zarf.yaml` |
| Vessels vertical | Active vertical demo wedge | `https://github.com/szl-holdings/vessels` and `uds-v0.2.0` release |

## What is intentionally not in the active demo

`counsel`, `terra`, and `carlota-jo` are funded-roadmap scaffolds. They remain
visible in the ecosystem registry for transparency, but the investor demo does
not present them as operational product surfaces.

The showcase also does **not** use the stale names `KORA`, `LUMINA`,
`PARAGON`, or active `Lyte` framing. The public story is anchored on the
repositories that actually exist in GitHub: `a11oy`, `amaru`, `sentra`,
`rosie`, `ouroboros`, `lutar-lean`, `ouroboros-thesis`, `uds-mesh`,
`vsp-otel`, `vessels`, `agi-forecast`, `szl-trust`, `szl-brand`,
`szl-cookbook`, `.github`, and `platform`.

## Architecture zoom-out

```mermaid
flowchart LR
    GH[GitHub canonical source<br/>code · CI · releases · manifests]
    HF[Hugging Face mirror<br/>generated diligence packet]
    UDS[UDS/Zarf operator lane<br/>package · manifest · attestations]
    INV[Investor / Warhacker demo<br/>proof-first walkthrough]

    GH -->|"pnpm payload:huggingface"| HF
    GH -->|"pnpm payload:bundle"| UDS
    HF --> INV
    UDS --> INV
    GH --> INV
```

```mermaid
flowchart TD
    A11OY[a11oy<br/>governed execution hub]
    PLATFORM[platform<br/>runtime integration]
    THESIS[ouroboros-thesis<br/>claim taxonomy + DOI]
    LEAN[lutar-lean<br/>Lean proof substrate]
    RUNTIME[ouroboros<br/>bounded-loop runtime]
    RECEIPTS[rosie + amaru<br/>receipt DAG + minting]
    OBS[sentra + vsp-otel<br/>drift + telemetry]
    MESH[uds-mesh<br/>bundle topology]
    VESSELS[vessels<br/>active vertical demo]
    TRUST[szl-trust<br/>public run artifacts]

    THESIS --> A11OY
    LEAN --> A11OY
    RUNTIME --> A11OY
    A11OY --> PLATFORM
    A11OY --> RECEIPTS
    RECEIPTS --> TRUST
    A11OY --> OBS
    A11OY --> MESH
    PLATFORM --> VESSELS
    OBS --> VESSELS
```

```mermaid
sequenceDiagram
    participant Operator
    participant A as A11oy
    participant P as Policy/Doctrine
    participant R as Receipt chain
    participant M as Manifest/UDS payload

    Operator->>A: request governed action
    A->>P: evaluate doctrine + policy constraints
    P-->>A: pass / escalate / reject
    A->>R: emit canonical operational receipt
    R-->>A: merkle root + previous hash
    A->>M: package proof artifacts for deploy/review
    M-->>Operator: SHA-256 manifest + attestation trail
```

## Evidence matrix

| Claim | Status | Evidence |
| --- | --- | --- |
| A11oy doctrine runtime checks execute locally | `verified-runtime` | `web/packages/a11oy-core/src/**/__tests__`, `pnpm test:doctrine` |
| QEC lineage primitives have standalone tests | `verified-runtime` | `packages/qec-integrity/src/qec_lineage.test.ts` |
| Operational receipts are hash-chained and verifiable | `verified-runtime` | `packages/receipt-substrate/src/index.ts`, `receipt_substrate.test.ts` |
| Deploy payload files are checksummed | `release-payload` | `deploy/MANIFEST.json`, `scripts/payload_manifest.py` |
| Hugging Face payload is source-generated | `release-payload` | `scripts/prepare_huggingface_payload.py` |
| Operational tarball has checksum sidecar | `release-payload` | `scripts/build_operational_payload.py` |
| Thesis v18.0 is the current claim anchor | `thesis-anchor` | DOI `10.5281/zenodo.20434276` |
| Lean proofs exist as a public substrate | `lean-backed-needs-current-ci` | `szl-holdings/lutar-lean`, DOI `10.5281/zenodo.20434308` |

## UDS / Warhacker proof point

The UDS story should be shown as an operator proof point:

1. Pull or build the A11oy payload.
2. Verify `MANIFEST.json` and the attestation chain.
3. Inspect the Zarf package metadata.
4. Run the receipt-chain smoke test.
5. Tamper with one payload file and show verification failure.
6. Tie the result back to the ecosystem readiness report and Hugging Face mirror.

The package should be described as **UDS/Zarf-compatible** and operator-ready
for proof-point review. Do not imply Defense Unicorns endorsement, catalog
acceptance, or partnership unless those become explicit public facts.

## Verification block

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

## Investor FAQ

### Is A11oy a model?

No. It is a governed execution fabric and payload discipline around model- or
agent-driven work. Hugging Face is used as a public diligence mirror, not as the
canonical release source.

### What makes it investable?

The substrate compounds: one policy/receipt/provenance layer supports multiple
verticals. The immediate demo path is A11oy + Vessels + UDS/Zarf packaging; the
receipt/proof/telemetry layers are reusable across the rest of the ecosystem.

### Where is the audit trail?

At three levels:

1. operational receipts in `packages/receipt-substrate`;
2. deploy checksums and attestations in `deploy/` and `artifacts/a11oy-uds/`;
3. public provenance and readiness status in `docs/PROVENANCE.md` and
   `docs/ecosystem-readiness-report.json`.

### Are all proof claims closed?

No broad proof-completeness claim should be made without current upstream proof
reports. The strong, truthful claim is that A11oy has a public proof substrate,
runtime tests, UDS payload manifests, and a claim contract that prevents
unsupported marketing language from becoming the public story.

