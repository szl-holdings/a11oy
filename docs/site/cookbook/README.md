<div align="center">

# szl-cookbook


<!-- series-a-badges (Doctrine v11) -->
[![Dependabot](https://img.shields.io/badge/Dependabot-enabled-025E8C?style=flat-square&logo=dependabot&logoColor=white)](https://github.com/szl-holdings/szl-cookbook/security/dependabot)


**Worked recipes + claude-code skills harvested with full provenance.**

[![Doctrine v11](https://img.shields.io/badge/Doctrine-v11-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-0B1F3A.svg?style=flat-square&logo=apache&logoColor=00D4FF)](https://www.apache.org/licenses/LICENSE-2.0) [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434308.svg)](https://doi.org/10.5281/zenodo.20434308)

[![CI](https://github.com/szl-holdings/szl-cookbook/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-cookbook/actions/workflows/ci.yml) [![Tests](https://github.com/szl-holdings/szl-cookbook/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-cookbook/actions/workflows/tests.yml) [![CodeQL](https://github.com/szl-holdings/szl-cookbook/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-cookbook/actions/workflows/codeql.yml) [![SBOM](https://github.com/szl-holdings/szl-cookbook/actions/workflows/sbom.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-cookbook/actions/workflows/sbom.yml) [![DCO](https://github.com/szl-holdings/szl-cookbook/actions/workflows/dco.yml/badge.svg?branch=main)](https://github.com/szl-holdings/szl-cookbook/actions/workflows/dco.yml) [![SLSA L1](https://img.shields.io/badge/SLSA-L1_(SBOM_%2B_DCO)-0B1F3A.svg?style=flat-square)](https://slsa.dev/spec/v1.0/levels) [![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/szl-holdings/szl-cookbook/badge)](https://securityscorecards.dev/viewer/?uri=github.com/szl-holdings/szl-cookbook) [![GHAS](https://img.shields.io/badge/GHAS-Code_Security-2DA44E.svg?style=flat-square&logo=github)](https://github.com/szl-holdings/szl-cookbook/security/code-scanning) [![ORCID](https://img.shields.io/badge/ORCID-0009--0001--0110--4173-A6CE39.svg?style=flat-square&logo=orcid&logoColor=white)](https://orcid.org/0009-0001-0110-4173)

[Hugging Face](https://huggingface.co/SZLHOLDINGS) · [GitHub Org](https://github.com/szl-holdings)

`receipts.in ≡ receipts.out`

</div>

---

<div align="center">

<!-- genius-hero (Doctrine v11) -->
<a href="https://szl-holdings.github.io/szl-cookbook/"><img src="assets/genius/cookbook_card.svg" alt="szl-cookbook — worked recipes with full provenance" width="860"></a>

<sub><b><a href="https://szl-holdings.github.io/szl-cookbook/">▶ Browse the live recipe carousel</a></b> — every recipe carries a HARVEST_LOG provenance receipt.</sub>

<img src="assets/genius/cookbook_cast.svg" alt="recipe run — khipu root → knot tag → PAC-Bayes bound" width="720">

</div>


> A measurable governance operator on the receipt-bus σ-algebra of agentic AI — demonstrated through worked recipes with PAC-Bayes bounds, carlota-jo doctrine guards, and claude-code skills with full HARVEST_LOG provenance.

---

## What this is

> **📖 The cookbook is live and reactivated.** Browse the full, customer-facing recipe library at
> **[github.com/szl-holdings/szl-cookbook](https://github.com/szl-holdings/szl-cookbook)** —
> 15 runnable recipes for the five flagships. Fastest start:
> **[Verify a receipt end-to-end](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/01-verify-a-receipt-end-to-end.md)**
> (cryptographically validates a real DSSE receipt in under a minute, no credentials).
>
> | Recipe | Flagship |
> |---|---|
> | [01 Verify a receipt end-to-end](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/01-verify-a-receipt-end-to-end.md) | amaru · a11oy · sentra |
> | [04 Drone counter-UAS verdict](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/04-drone-counter-uas-verdict.md) | killinchu |
> | [05 Memory-attested reasoning](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/05-memory-attested-reasoning.md) | amaru |
> | [06 Verify cosign + Rekor (SLSA L1)](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/06-cosign-rekor-slsa-l1.md) | all 5 |
> | [12 Doctrine ledger query](https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/12-doctrine-ledger-query.md) | all 5 |
>
> Full index: [szl-cookbook/recipes](https://github.com/szl-holdings/szl-cookbook/tree/main/recipes).



**szl-cookbook** provides executable recipes and SKILL.md patterns for engineering teams building governed AI applications on the SZL substrate. Two flagship recipes demonstrate the full stack: `knot-calculus-v1` implements the khipu receipt DAG with a McAllester-1999 PAC-Bayes bound and TH11 knot-invariant verification; `anatomy-evolved-v1` covers the 8-organ anatomy with carlota-jo doctrine guards for adversarial prompt defense. Nine claude-code skills are provided with HARVEST_LOG provenance, each a `SKILL.md` agent-instruction pattern harvested from real production sessions.

## Why it matters

Governed AI requires more than a policy engine — it requires executable examples that engineers can copy, adapt, and verify. szl-cookbook closes the gap between the Ouroboros Thesis formal guarantees and working code: every recipe is `tsc --noEmit` clean, references specific Lean obligations by theorem name, and carries a sealed date. The Doctrine v11 ban-word CI check runs on every push.

## Quickstart

```bash
pnpm install
pnpm exec:recipe governance/policy-gate-scaffold
pnpm doctrine:check   # Doctrine v11 ban-word sweep
```

Run the knot-calculus demo:

```bash
cd recipes/knot-calculus-v1/code
npx tsx tests/demo.ts
# Prints: khipu root receipt → knot-invariant tag → PAC-Bayes bound → TH11 failure demo
```

## Key files

| Path | Role |
|------|------|
| `recipes/knot-calculus-v1/` | Knot calculus recipe: khipu receipt DAG, PAC-Bayes bound (McAllester-1999), TH11 knot-invariant tag emitter |
| `recipes/knot-calculus-v1/code/src/pac-bayes-bound.ts` | McAllester-1999 PAC-Bayes upper bound implementation |
| `recipes/knot-calculus-v1/code/src/khipu-receipt.ts` | Khipu-indexed receipt DAG with sum-of-sums invariant |
| `recipes/knot-calculus-v1/code/src/knot-tag.ts` | Audit-Reidemeister knot-invariant tag emitter |
| `recipes/anatomy-evolved-v1/` | 8-organ anatomy recipe with carlota-jo doctrine guard |
| `recipes/anatomy-evolved-v1/thesis_ch9_anatomy_evolved_v1.md` | Chapter 9 — per-organ evolution, Lean obligations, Series A test evidence |
| `recipes/anatomy-evolved-v1/payloads/` | Operational payloads: main (3,735 lines), thesis injection (2,511 lines), explainer agent (1,964 lines) |
| `recipes/anatomy-evolved-v1/code/` | Extracted TypeScript + Lean tree — `tsc --noEmit` clean, 25/25 smoke tests |
| `skills/commit-hygiene/SKILL.md` | Claude-code skill: commit hygiene |
| `skills/dead-code-detector/SKILL.md` | Claude-code skill: dead code detection |
| `skills/debug-protocol/SKILL.md` | Claude-code skill: debug protocol |
| `skills/dependency-health/SKILL.md` | Claude-code skill: dependency health |
| `skills/doc-comment-hygiene/SKILL.md` | Claude-code skill: doc comment hygiene |
| `skills/monorepo-impact-analysis/SKILL.md` | Claude-code skill: monorepo impact analysis |
| `skills/pre-flight-thinking/SKILL.md` | Claude-code skill: pre-flight thinking |
| `skills/react-component-review/SKILL.md` | Claude-code skill: React component review |
| `skills/typescript-refactor/SKILL.md` | Claude-code skill: TypeScript refactor |
| `meta/content-gap-matrix-2026-05-17.md` | Content gap matrix — recipe coverage vs. thesis obligations |

## Doctrine v11

A ban-word CI check runs on every push via `.github/workflows/doctrine.yml`. The full list of prohibited superlatives is defined in the workflow file. Any match causes CI failure.

## Related

| Repo | Role |
|------|------|
| [ouroboros](https://github.com/szl-holdings/ouroboros) | Core runtime |
| ouroboros-thesis | Formal research paper (DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)) |
| [lutar-lean](https://github.com/szl-holdings/lutar-lean) | Lean 4 proofs — 749 decls / 15 raw axioms / 163 sorries @ HEAD c7c0ba17 |
| [uds-mesh](https://github.com/szl-holdings/uds-mesh) | UDS service mesh integration |
| [vsp-otel](https://github.com/szl-holdings/vsp-otel) | OTel + DSSE exporter |
| [a11oy](https://github.com/szl-holdings/a11oy) | Flagship governance app |
| amaru | Cardano anchoring layer |
| sentra | Policy enforcement engine |
| Hatun Doctrine Specification | [szl-holdings/platform/docs/a11oy/spec/hatun-doctrine-spec/](https://github.com/szl-holdings/platform/tree/main/docs/a11oy/spec/hatun-doctrine-spec/) |

## On Hugging Face

[SZLHOLDINGS on Hugging Face](https://huggingface.co/SZLHOLDINGS) — Spaces · datasets · models

| Surface | Artifact |
|---------|----------|
| Live demo | [szl-cookbook-runner](https://huggingface.co/spaces/SZLHOLDINGS/szl-cookbook-runner) · [szl-cookbook-platform](https://huggingface.co/spaces/SZLHOLDINGS/szl-cookbook-platform) |
| Deep-dive | [szl-cookbook-deep-dive](https://huggingface.co/spaces/SZLHOLDINGS/szl-cookbook-deep-dive) |
## Citation

See [CITATION.cff](./CITATION.cff) for machine-readable metadata. Quick reference:

```
S. P. Lutar Jr., "szl-cookbook — Worked recipes + claude-code skills with full provenance for governed AI systems,"
SZL Holdings, 2026. https://github.com/szl-holdings/szl-cookbook
```

Preferred citation: [The Ouroboros Substrate (v18.0)](https://doi.org/10.5281/zenodo.20434276), DOI 10.5281/zenodo.20434276.

## License · Trust · Security

[Apache 2.0](./LICENSE). SLSA Level 1 (source + build provenance documented; L2/L3 require Sigstore + isolated builders — roadmap). Security disclosures: see [SECURITY.md](./SECURITY.md).

## SZL Holdings

![SZL Holdings](./branding/szl-avatar-animated.gif)

*Amaru — the Inca avatar of SZL Holdings. Animated mark (400×400, 16fps loop). Signed Yachay.*
