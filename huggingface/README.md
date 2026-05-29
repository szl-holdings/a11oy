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

## What ships

| Surface | Contents |
| --- | --- |
| `source/` | README, roadmap, changelog, ecosystem map, provenance contract. |
| `payloads/deploy/` | `zarf.yaml`, `attestations.jsonl`, and per-file `MANIFEST.json`. |
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
pnpm payload:verify
pnpm payload:huggingface
pnpm payload:bundle
pnpm payload:bundle:verify
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
  `docs/ecosystem-registry.json`
- **Payload discipline:** Python-native manifesting, deterministic tarball,
  SHA-256 sidecar, DCO, CodeQL, SBOM, Trivy, docs, and secret scan

See `source/docs/PROVENANCE.md` and `source/docs/ECOSYSTEM.md` for the
claim-status contract and repository readiness map.

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

## Operational status

The canonical release, CI, and provenance records remain in GitHub. Hugging Face
is used as a public discovery and distribution surface for the Series-A review
packet and operator payload metadata.
