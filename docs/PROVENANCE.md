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
| `lean-backed-current-green` | Claim maps to a Lean module and a current upstream proof report / CI run verifies that module. | “Lean-backed in `<module>` with current green proof report” |
| `lean-backed-needs-upstream-ci` | Claim maps to the Lean proof substrate, but the latest observed upstream proof CI or release state must be reconciled before broad all-green language is used. | “proof-substrate-backed; current proof CI must be checked before repeating all-green claims” |
| `release-payload` | Claim is present in signed or checksummed release payloads. | “included in operational payload” |
| `thesis-anchor` | Claim is part of the DOI-pinned thesis / claim taxonomy and may guide implementation language. | “anchored to the Ouroboros Thesis v18.0 DOI” |
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
| UDS/Zarf-compatible operator proof point | `release-payload` | `artifacts/a11oy-uds/README.md`, `docs/WARHACKER_UDS_PROOF_POINT.md` |
| Ecosystem readiness map | `verified-runtime` | `docs/ecosystem-readiness-report.json`, `pnpm ecosystem:readiness` |

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
- Do not use stale product-name framing (`KORA`, `LUMINA`, `PARAGON`, or active
  `Lyte`) in the A11oy/Hugging Face showcase. Center the real GitHub repos.
- Counsel, Terra, and Carlota Jo are funded-roadmap scaffolds and must not be
  presented as operational demo surfaces until that changes.
- UDS/Zarf language should be precise: “UDS/Zarf-compatible proof point” and
  “operator handoff” are acceptable; Defense Unicorns endorsement, catalog
  acceptance, or universal UDS deployability require separate public evidence.

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
