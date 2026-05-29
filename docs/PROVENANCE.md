# A11oy provenance and public-claim contract

This document is the operator-facing provenance contract for A11oy. It is meant
to keep GitHub, release payloads, and Hugging Face mirrors aligned with the
current thesis/proof state before any external push.

## Canonical references

| Layer | Canonical reference |
| --- | --- |
| A11oy source | <https://github.com/szl-holdings/a11oy> |
| Ouroboros Thesis current version | v18.0 |
| Ouroboros Thesis version DOI | <https://doi.org/10.5281/zenodo.20434276> |
| Ouroboros Thesis concept DOI | <https://doi.org/10.5281/zenodo.19944926> |
| Lean proof software DOI | <https://doi.org/10.5281/zenodo.20434308> |
| Principal author ORCID | <https://orcid.org/0009-0001-0110-4173> |
| Hugging Face target | `SZLHOLDINGS/a11oy-v19-substrate` |

## Claim status language

Use the following language in GitHub, release payloads, and Hugging Face cards.

| Status | Meaning | Allowed wording |
| --- | --- | --- |
| `verified-runtime` | Runtime code and tests in this repo pass CI. | “validated by A11oy Doctrine Build” |
| `lean-backed` | Claim maps to a Lean module and is included in the public proof/provenance set. | “Lean-backed” |
| `release-payload` | Claim is present in signed or checksummed release payloads. | “included in operational payload” |
| `roadmap` | Planned or partially implemented; do not present as shipped. | “planned”, “tracked”, “next” |
| `historical` | Older thesis/doc language retained for context. | “historical”, “legacy” |

## Current A11oy guarantees

| Guarantee | Status | Local evidence |
| --- | --- | --- |
| KS-18 2-regular cover | `verified-runtime` | `web/packages/a11oy-core/src/quantum/__tests__/kochen-specker-18.test.ts` |
| KS-18 empty-observation unsatisfiability | `verified-runtime` | `pnpm test:doctrine` |
| Q15 quaternion token behavior | `verified-runtime` | `web/packages/a11oy-core/src/governance/__tests__/quaternion-state.test.ts` |
| PAC-Bayes / Madhava governance bounds | `verified-runtime` | `web/packages/a11oy-core/src/governance/__tests__/*` |
| LID threshold checks | `verified-runtime` | `web/packages/a11oy-core/src/governance/__tests__/lid-check.test.ts` |
| Deploy payload per-file SHA-256 manifest | `release-payload` | `deploy/MANIFEST.json`, `pnpm payload:verify` |
| Operational tarball and checksum sidecar | `release-payload` | `pnpm payload:bundle`, `pnpm payload:bundle:verify` |

## Claims to keep guarded

- Agent-loop termination and Lambda monotonicity should only be described as
  shipped when the exact Lean module/path and CI status are pinned in the
  payload metadata.
- TH10 uniqueness and related Cauchy-style uniqueness claims should be described
  as thesis/proof-roadmap unless the current Lean source reports them closed.
- “Zero sorry” or “all GREEN” statements should be backed by a machine-readable
  proof report from `lutar-lean`; otherwise use precise module/test language.
- Hugging Face is a distribution mirror and diligence surface, not the canonical
  source of release truth. GitHub releases, checks, manifests, and checksums stay
  canonical.

## Payload inclusion

The Python operational payload builder includes this document, the ecosystem
registry, deploy manifests, built doctrine outputs, and the prepared Hugging Face
payload under `dist/payload/a11oy-operational-payload.tar.gz`.

Verify before publishing:

```bash
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
pnpm ecosystem:audit
pnpm payload:verify
pnpm payload:bundle
pnpm payload:bundle:verify
```
