# The Lutar Invariant — Ouroboros Thesis v3 — One-Pager

**Stephen P. Lutar — SZL Holdings — 2026-05-02 — ORCID 0009-0001-0110-4173**
**DOI** [10.5281/zenodo.19983066](https://doi.org/10.5281/zenodo.19983066) · **Concept DOI** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)
**License** CC BY 4.0 · **Reference impl.** [github.com/szl-holdings/szl-holdings-platform](https://github.com/szl-holdings/szl-holdings-platform)

## What

Nine runtime axes, weighted geometric mean, Egyptian-fraction inspectable weights, four proved axioms (22/22 numerical witnesses).

## Abstract (short)

We define the Lutar Invariant \( \Lambda \), a scalar trust aggregator over nine independent runtime axes: \[
\Lambda(\mathbf{x}; \mathbf{w}) = \prod_{i=1}^{9} x_i^{w_i}, \qquad x_i \in [0,1], \quad w_i \geq 0, \quad \sum_{i=1}^{9} w_i = 1.
\] \(\Lambda\) is the weighted geometric mean of nine axis scores, with weights drawn from a transparent Egyptian unit-fraction decomposition. We give four axioms — monotonicity (A1), zero-pinning (A2), Egyptian inspectability (A3), and page-curve concavity (A4) — and prove each by explicit numerical witness. The proof suite (22 assertions, all passing) is shipped in the public reference implementation under an open-source license, and reproducible via pnpm install && pnpm exec vitest run packages/ouroboros/src/lutar-invariant-proof.test.ts. The contribution is the specific combination: weighted-geometric (not arithmetic) aggregation, distinct unit-fraction weights chosen for inspectability, an explicit four-axiom set, and a public falsifiable test surface. To the author's knowledge, this combination is novel; related work on multi-axis trust scor

## Motivation (excerpt)

Bounded-loop AI runtimes accumulate trust signals across heterogeneous concerns: data freshness, source priority, validator passes, risk-tier escalation, operator approval, and others. Practitioners increasingly need a single scalar summary of these signals — for halt conditions, for receipt generation, for audit trails — yet most deployed systems use either an unaxiomatized weighted sum or a learned black-box score [Bradatsch et al. 2024; Mahmood et al. 2023]. Three properties distinguish a useful trust aggregator from an arbitrary scoring function: 1. Monotonicity. Improving any axis must not lower the score.
2. Zero-pinning. A single failed axis with positive weight must drive the score to zero — otherwise the aggregator can mask catastrophic failure of one dimension by averaging it wit

## What this paper does not claim

Stating limitations explicitly is part of the contribution. 1. Domain of validity. The axiom proofs are numerical witnesses on finite test points. They establish that the IEEE-754 implementation satisfies the axioms on the points exercised; they do not constitute formal-logic proofs over all of \([0,1]^9\). A future companion in a proof assistant (Coq, Lean) would close this gap; the closed-form structure of \(\Lambda\) makes such a proof straightforward but it has not yet been done. 2. Axis labels are not proven meaningful. The nine axis labels (cleanliness, horizon, resonance, frustum, geometry, invariance, moral, being, non_measurability) are runtime-system commitments. This paper does no

## Companion DOIs

| Version | DOI |
|---|---|
| v1 | [10.5281/zenodo.19867281](https://doi.org/10.5281/zenodo.19867281) |
| v2 | [10.5281/zenodo.19934129](https://doi.org/10.5281/zenodo.19934129) |
| v3 | [10.5281/zenodo.19983066](https://doi.org/10.5281/zenodo.19983066) |
| v9 | [10.5281/zenodo.20053148](https://doi.org/10.5281/zenodo.20053148) |
| v10 | [10.5281/zenodo.20053163](https://doi.org/10.5281/zenodo.20053163) |
| v11 | [10.5281/zenodo.20119582](https://doi.org/10.5281/zenodo.20119582) |

## Citing

```bibtex
@article{lutar2026ouroboros_v3,
  author    = {Lutar, Stephen P.},
  title     = {The Loop Is the Product: Measuring Bounded Recursion as a System Primitive for Auditable AI},
  year      = 2026,
  month     = may,
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.19983066},
  url       = {https://doi.org/10.5281/zenodo.19983066}
}
```
