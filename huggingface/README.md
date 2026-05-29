---
license: other
license_name: proprietary
license_link: https://github.com/szl-holdings/a11oy/blob/main/LICENSE
language:
  - en
tags:
  - governance
  - agentic-ai
  - policy
  - provenance
  - zarf
  - uds
  - series-a
  - operational-payload
pretty_name: A11oy Governed Agentic Execution Fabric
---

# A11oy — governed execution fabric

**A11oy is not a model checkpoint.** It is a governed execution substrate:
policy gates, signal measurement, knowledge routing, QEC-derived receipt
integrity, and an operational payload that can be verified from GitHub.

This Hugging Face mirror is the public showcase layer for the A11oy operational
packet. GitHub remains the canonical source of truth for code, CI, SBOM, SLSA,
DCO, deploy manifests, checksums, and release provenance.

## One-line thesis

A11oy turns agentic actions into governed, reviewable, receipt-backed decisions:
**every action passes through doctrine checks, every payload is checksummed, and
every public claim is tied back to a provenance contract.**

```mermaid
flowchart LR
    GH[GitHub canonical source<br/>CI · releases · manifests · proofs]
    PAYLOAD[Generated HF payload<br/>README · reports · demo receipts]
    REVIEW[Investor / operator review<br/>Series-A · UDS · Warhacker]

    GH -->|"pnpm payload:huggingface"| PAYLOAD
    PAYLOAD --> REVIEW
    GH --> REVIEW
```

## What ships

| Surface | Contents |
| --- | --- |
| `SHOWCASE.md` | Exhaustive capability map, architecture diagrams, and active repo graph. |
| `INVESTOR_BRIEF.md` | Series-A narrative with proof/evidence links and scoped caveats. |
| `VERIFICATION.md` | Exact local verification commands and what each command proves. |
| `INNOVATIONS_DEEP_DIVE.md` | Evidence-backed implementation deep dive; no unsupported model/API claims. |
| `INTEGRATION_QUICKSTART.md` | Current TypeScript/package/payload quickstart. |
| `EVAL_TRACE_SAMPLE.jsonl` | Two-line receipt sample generated from the current `packages/receipt-substrate` schema and covered by receipt-substrate tests. |
| `source/` | README, roadmap, changelog, ecosystem map, investor demo, provenance contract. |
| `payloads/deploy/` | `zarf.yaml`, Kubernetes manifests, `attestations.jsonl`, and per-file `MANIFEST.json`. |
| `build/` | Root workspace metadata and lockfile used by the doctrine lane. |
| `a11oy-metadata.json` | Source commit, branch, verification commands, and payload map. |

The GitHub Actions operational bundle additionally includes built doctrine
package outputs and a tarball-level manifest/checksum sidecar.

## Verification commands

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

The current Doctrine Build workflow runs this lane and uploads
`a11oy-operational-payload.tar.gz` plus `a11oy-operational-payload.tar.gz.sha256`
as a GitHub Actions artifact.

## Series-A diligence packet

- **Operational hub:** `a11oy`
- **Runtime monorepo:** `platform`
- **Thesis anchor:** Ouroboros Thesis v18.0, DOI `10.5281/zenodo.20434276`
- **Proof substrate:** `lutar-lean`, DOI `10.5281/zenodo.20434308`
- **Org coverage:** 19 visible public `szl-holdings` repos in
  `source/docs/ecosystem-registry.json`, with demo readiness in
  `source/docs/ecosystem-readiness-report.json`
- **Payload discipline:** Python-native manifesting, deterministic tarball,
  SHA-256 sidecar, DCO, CodeQL, SBOM, Trivy, docs, and secret scan
- **UDS / Zarf lane:** package and operator proof point are documented in
  `source/docs/WARHACKER_UDS_PROOF_POINT.md`

See `source/docs/PROVENANCE.md` and `source/docs/ECOSYSTEM.md` for the
claim-status contract and repository readiness map.

## Active showcase scope

This packet centers the public repos with active demo or supporting evidence:
`a11oy`, `amaru`, `sentra`, `rosie`, `ouroboros`, `lutar-lean`,
`ouroboros-thesis`, `uds-mesh`, `vsp-otel`, `vessels`, `agi-forecast`,
`szl-trust`, `szl-brand`, `szl-cookbook`, `.github`, and `platform`.

`counsel`, `terra`, and `carlota-jo` are intentionally marked
funded-roadmap/excluded in the readiness report. This mirror does not use stale
product-name framing such as KORA, LUMINA, PARAGON, or active Lyte copy.

## What this is not

- Not an LLM host.
- Not a training dataset.
- Not a replacement for GitHub Releases, SBOMs, SLSA attestations, or signed UDS
  payloads.
- Not a claim that every thesis statement is fully closed in Lean; public claims
  are gated by the provenance contract.

## Canonical source

- GitHub: <https://github.com/szl-holdings/a11oy>
- DOI: <https://doi.org/10.5281/zenodo.20434276>
- Ecosystem map: <https://github.com/szl-holdings/a11oy/blob/main/docs/ECOSYSTEM.md>
- Provenance contract: <https://github.com/szl-holdings/a11oy/blob/main/docs/PROVENANCE.md>
- Investor demo: <https://github.com/szl-holdings/a11oy/blob/main/docs/INVESTOR_DEMO.md>

## Operational status

The canonical release, CI, and provenance records remain in GitHub. Hugging Face
is used as a public discovery and distribution surface for the Series-A review
packet and operator payload metadata.
