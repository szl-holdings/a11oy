# Math lineage runtime map

This map connects the mathematical and historical sources used in the thesis to
the runtime surfaces that are actually present in A11oy today. It is a
showcase document, but it is not marketing copy: every row carries evidence and
a claim caveat.

## Lineage to runtime

| Lineage | Formula / theorem hook | Runtime hook | Claim status |
| --- | --- | --- | --- |
| Inka khipu / knot receipts | `rootValue = Σ pendantValue`; TH11 Khipu summation invariant in `lutar-lean` | `summationInvariantGate()` and receipt DAG/Khipu surfaces in Rosie | Runtime gate is real; knot/chord correspondence remains structural lineage unless exact theorem path is cited. |
| Egyptian / Akhmim / Rhind | Rhind Mathematical Papyrus `2/n` unit fractions; false-position calibration | `akhmim-table` verifier and `falsePositionGate()` | Runtime-verified; full historical table Lean coverage is representative unless exact Lean theorem says otherwise. |
| Liu Hui | Polygon recurrence for π approximation, `sideSquared_bounds` | `liuHuiPiGate()` threshold check | Bounded recurrence is runtime-gated; convergence remains axiom/tracked in Lean. |
| Madhava | Alternating arctan series and remainder bound | `madhavaBoundGate()` and `madhavaPACBayesRefinement` | Nonnegativity/monotonicity are evidenced; full arctan specialization still has tracked sorries. |
| Cauchy / Banach | TH10 uniqueness route and contraction/fixed-point lineage | `lutar-lean` uniqueness/proof substrate; DPO/Banach references | TH10 is not closed; do not claim Cauchy uniqueness without current proof report. |
| Shannon / DPI | Doctrine label entropy, rate bound, data-processing inequality | `a11oy` provenance docs, UDS/HF guardrails, future named gates | Shannon label code is evidenced; broad DPI receipt-chain proof is tracked until Lean is green. |
| Feynman / Witten / Bar-Natan / knots | Audit-Reidemeister and Feynman lineage records | `lutar-lean` proof lineage, Khipu/receipt DAG runtime analogues | Citation chain and analogy are evidenced; audit-Reidemeister invariance remains conjectural/tracked. |
| Wheeler | Delayed-choice closure / receipt window | `lutar-lean` Wheeler module; UDS receipt closure narrative | Proof substrate present; TS runtime hook is staged unless wired into receipt path. |
| Preskill / Kitaev / QEC | POVM completeness, Hamming/Shor/CSS/Kitaev parity | `web/packages/a11oy-core/src/quantum`, `packages/qec-integrity`, `adversarialRobustnessGate` caveat | Runtime tests are real; quantum-threshold theorems are not blanket formal claims. |

## Operational principle

```mermaid
flowchart LR
    Source[Historical / mathematical source]
    Thesis[Ouroboros Thesis claim]
    Lean[lutar-lean theorem or tracked obligation]
    Runtime[A11oy runtime gate / receipt]
    Evidence[CI test / manifest / payload]

    Source --> Thesis --> Lean --> Runtime --> Evidence
```

If any arrow is missing, the claim must be marked `roadmap`,
`lean-backed-needs-upstream-ci`, or `historical` per
[`PROVENANCE.md`](PROVENANCE.md).

## What to say

Use:

- “runtime-checked historical mathematics hooks”
- “proof-substrate-backed where exact modules are cited”
- “tracked obligation” when the Lean work is staged
- “operator proof point” for UDS until signed assets and UDS Package CRs exist

Avoid:

- “all proof work is closed”
- “zero sorry”
- “full Cauchy uniqueness proved”
- “full Liu Hui convergence proved”
- “Defense Unicorns catalog accepted”
- “quantum threshold theorem implemented”

