# Series-A market evidence — governed AI diligence map

This file turns public standards and market expectations into an evidence map
for the A11oy investor demo. It is not a certification claim. It shows where the
repo already has reviewable artifacts and where production work remains.

## External signals used

| Source | Public signal | A11oy response | Current evidence | Gap / caveat |
| --- | --- | --- | --- | --- |
| NIST AI Risk Management Framework | AI risk programs need govern, map, measure, and manage functions for trustworthy AI. | A11oy frames governed execution as policy gates, measurement, provenance, and managed payload release. | `docs/PROVENANCE.md`, `docs/ecosystem-readiness-report.json`, `npm run test:runtime` | Not a NIST certification; map exact customer controls during deployment. |
| EU AI Act, Regulation (EU) 2024/1689 | High-risk AI emphasizes risk-based obligations, technical documentation, transparency, record keeping, and human oversight. | A11oy shows receipt chains, claim-status language, and human-review/operator proof points. | `packages/receipt-substrate`, `huggingface/DEMO_RECEIPT_SAMPLE.jsonl`, `docs/INVESTOR_DEMO.md` | Customer-specific EU AI Act classification and legal review remain deployment work. |
| CISA SBOM guidance | SBOMs support software supply-chain transparency and machine-processable risk analysis. | A11oy keeps SBOM workflows, payload manifests, and deterministic bundles in the diligence path. | `.github/workflows/sbom.yml`, `deploy/MANIFEST.json`, `pnpm payload:bundle:verify` | SBOM assets do not equal signed deployment payloads; v0.3.x signed assets need owner-side release evidence. |
| SLSA framework | Provenance levels are progressive; higher claims require signed provenance and hardened build evidence. | A11oy uses honest SLSA language and avoids L3 claims unless the workflow evidence exists. | README SLSA badge, `.github/workflows/slsa.yml`, `.github/workflows/doctrine.yml` | SLSA L2/L3 should remain PR/roadmap until merged workflow evidence is green. |
| Model Cards for Model Reporting | Public AI artifacts should disclose intended use, performance context, limitations, and responsible-use boundaries. | The Hugging Face mirror acts as a model-card-like diligence packet while explicitly saying A11oy is not a model checkpoint. | `huggingface/README.md`, `huggingface/VERIFICATION.md`, `huggingface/INVESTOR_BRIEF.md` | HF is a mirror, not canonical release truth; stale remote files must be pruned on publish. |

## The Series-A wedge

A11oy is strongest when presented as a control fabric for regulated AI work:

1. **Govern:** policy gates, claim-status language, and excluded-scope tables.
2. **Map:** ecosystem registry and readiness report across 19 public repos.
3. **Measure:** doctrine tests, QEC tests, receipt tests, and payload verification.
4. **Manage:** deterministic operational bundle, SBOM lane, and guarded HF mirror.

This is the investor-safe story: A11oy makes agentic execution reviewable before
it becomes customer impact. It does not need to pretend to be a model, a finished
UDS catalog product, or a fully closed Lean proof corpus.

## What must be real before production

| Gate | Required evidence |
| --- | --- |
| Signed deployment payloads | Release assets with tarball, `.sig`, `.sha256`, public key, and verification command. |
| GHCR deployment path | Public or authenticated image/package pull proof tied to the same release line. |
| Customer controls | Deployment-specific threat model, retention policy, access control, and legal classification. |
| Formal proof claims | Current upstream `lutar-lean` proof report for exact theorem/module claims. |
| HF publication | `pnpm payload:huggingface` output published with stale remote files pruned. |

## Public references

- NIST AI Risk Management Framework: <https://www.nist.gov/itl/ai-risk-management-framework>
- EU AI Act text: <https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng>
- CISA SBOM minimum elements: <https://www.cisa.gov/resources-tools/resources/2025-minimum-elements-software-bill-materials-sbom>
- SLSA framework: <https://slsa.dev/>
- Model Cards for Model Reporting: <https://arxiv.org/abs/1810.03993>
