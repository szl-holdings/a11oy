# Ancient texts and formula lineage

This document records ancient and pre-modern source lineages that can be used
inside the A11oy ecosystem without hallucinated “secret decoding” claims. The
rule is simple: an ancient text may inspire a runtime model only when the
connection can be stated as a verifiable mathematical or operational pattern.

## Doctrine boundary

- Do not claim the Dead Sea Scrolls, Emerald Tablet, khipu, Rhind Papyrus, or
  any ancient source “contains” A11oy.
- Do not claim hidden codes, secret proofs, or direct historical continuity
  unless a cited scholarly source supports that exact statement.
- Do use source lineages as evidence for durable mathematical patterns:
  calendars, ledgers, unit fractions, false position, recurrence, bounded
  approximation, summation, correspondence, and audit loops.
- Runtime claims must still point to code, tests, receipts, manifests, or Lean
  modules.

## Source lineage table

| Source | Scholarly anchor | Pattern | A11oy formula/runtime hook | Claim status |
| --- | --- | --- | --- | --- |
| Dead Sea Scrolls / Qumran calendrical texts | Qumran contains calendrical texts, including a schematic 364-day calendrical tradition and priestly-service/lunar cycles discussed in scholarship by VanderKam, Ben-Dov, Talmon, and others. | Rule-governed time, cyclic service rotations, schedule integrity. | Future scheduler/receipt-window checks can cite this only as calendrical lineage; current Wheeler window is the stronger runtime hook. | `historical` / `roadmap` |
| Emerald Tablet / Hermetic corpus | The text appears in Arabic/Latin Hermetic transmission; “as above, so below” is a later/Latin idiom, while earlier Arabic readings emphasize above/from-below relational emergence. | Correspondence between levels; macro/micro mapping; emergence across layers. | Use only as analogy for cross-layer provenance, never as proof. Better runtime anchors are CrossComponentInvariant and receipt-chain provenance. | `historical` |
| Rhind Mathematical Papyrus | The Rhind/Ahmes papyrus contains the `2/n` unit-fraction table and false-position problems 24–29. | Unit-fraction decomposition and proportional correction. | `akhmim-table` verifier and `falsePositionGate`. | `verified-runtime` for code; Lean full-table status must be cited precisely. |
| Inka khipu | Ascher & Ascher and Urton document khipu numerical/accounting structures, hierarchy, and summation relationships. | Pendant/root summation, ledger hierarchy, tamper-evident totals. | `summationInvariantGate`; Rosie Khipu receipt DAG. | `verified-runtime` for gate; broader narrative encoding remains guarded. |
| Liu Hui / Nine Chapters commentary | Liu Hui’s polygon-doubling method approximates π by increasingly fine polygons. | Bounded iterative approximation. | `liuHuiPiGate` enforces numeric threshold on π approximation. | `verified-runtime`; convergence remains guarded unless Lean proof is current. |
| Madhava / Kerala school | Madhava/Kerala school arctangent and trigonometric series appear in later sources such as Yuktibhāṣā and Tantrasangraha commentaries. | Alternating series and remainder bounds. | `madhavaBoundGate`; `madhavaPACBayesRefinement`. | `verified-runtime` for bound checks; full arctan Lean closure remains guarded. |
| Newton / Cauchy / Banach | Newton/Gregory/Leibniz calculus lineage, Cauchy functional equation, Banach contraction. | Series, uniqueness, convergence, fixed-point stability. | TH10 uniqueness route, DPO stability, PAC-Bayes/Madhava refinements. | `lean-backed-needs-upstream-ci` for TH10 until CAUCHY_ND closes. |
| Shannon / Wheeler / Feynman | Shannon information theory, Wheeler delayed-choice, Feynman path integral / diagram lineage. | Entropy bounds, delayed audit closure, sum-over-paths analogy. | Doctrine entropy, Wheeler window, Feynman audit sum modules. | Use exact module status; some Feynman/Reidemeister claims are conjectural. |
| Kitaev / Preskill / QEC | Quantum error-correction and POVM sources. | Parity, syndrome checks, completeness. | `qec-integrity`, `quantum/povm`, CSS/Kitaev runtime parity tests. | `verified-runtime` for runtime tests; not a blanket quantum threshold proof. |

## How to turn lineage into runtime

```mermaid
flowchart LR
    Text[Ancient or historical source]
    Pattern[Verifiable pattern]
    Formula[Formula / theorem]
    Gate[Runtime gate]
    Receipt[Receipt / manifest evidence]

    Text --> Pattern --> Formula --> Gate --> Receipt
```

If a row cannot reach `Receipt`, keep it out of active-demo claims.

## Candidate upgrades

| Upgrade | Why it matters | Safe next step |
| --- | --- | --- |
| Calendrical receipt windows | Qumran calendar lineage maps cleanly to bounded audit windows and periodic service rotations. | Add a roadmap issue/doc only; do not claim implementation until scheduler code exists. |
| Hermetic correspondence as provenance metaphor | Cross-layer “above/from below” maps to theorem→gate→receipt traceability. | Keep as historical analogy in docs, not as proof or product copy. |
| Khipu receipt DAG | Already the strongest ancient-text runtime lineage. | Ensure all Khipu claims cite `summationInvariantGate` and Rosie receipt tests. |
| Rhind/Akhmim operator demo | Easy investor demo: false-position + unit-fraction checks are understandable. | Keep `akhmim-table` and `falsePositionGate` exported and tested. |
| Madhava/Liu Hui convergence gates | Shows pre-modern numerical analysis as runtime safety checks. | Keep Lean caveats visible; runtime thresholds are the operational surface. |

## Do not say

- “The Dead Sea Scrolls prove A11oy.”
- “The Emerald Tablet encodes the doctrine.”
- “All ancient traditions predicted this system.”
- “All Lean proofs are closed.”
- “The quantum threshold theorem is implemented.”

## Use instead

“A11oy operationalizes durable mathematical patterns — ledger summation,
bounded approximation, proportional correction, recurrence, entropy, parity,
and receipt closure — with runtime gates and provenance receipts. Historical
sources are cited as lineage where appropriate; GitHub code, tests, manifests,
and Lean modules remain canonical.”

