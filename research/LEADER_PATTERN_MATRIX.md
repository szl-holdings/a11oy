# Leader Pattern Matrix — study leaders, rebuild originally

Method deliverable for the Codex v3 program (2026-10-01). Each row: the public
method studied, the invariant abstracted from it, its attribution, and the SZL
recomposition through receipts and Lambda gates. Clean-room: no code taken;
only the invariant, rebuilt in estate primitives. A pattern is KEPT only after
an ablation over >= 3 seeds with confidence intervals (program method) — until
then every row is PROPOSAL.

| # | Leader (attribution) | Invariant abstracted | SZL recomposition | Status |
|---|---|---|---|---|
| 1 | Ai2 OLMo fully-open training (allenai/OLMo) | "Open" means the full stack — data, code, checkpoints, logs — or the claim is uncheckable | estate publishes data manifests, seeds, and receipts next to every weight; CARD_ONLY fails discovery | FACT (discovery enforces) |
| 2 | OpenSSF model signing / Sigstore (sigstore/model-transparency) | artifact integrity is verifiable by a third party offline | brainreceipt ECDSA-P256 signed inference receipts; brainverdict composes + signs the chain | FACT (live) |
| 3 | SLSA / in-toto provenance | every build step is recorded and tamper-evident, not just the output | hash-chained ledgers (quarantine ledger; ci-witness-action receipts); QUANT_MANIFEST binds parent revision live | FACT (scaffolded; parity receipts BLOCKED pending local GPU) |
| 4 | Conformal abstention (Angelopoulos et al.; AbstentionBench 2025 measurement) | a model should abstain with a calibrated, measurable rate — not answer everything | braineval probe battery + fabrication gate (CI-measured refusal posture, 0.97 ceiling, MEASURED only) | FACT (gate live; first run measured refusal rate 0.5 — surfaced, not hidden) |
| 5 | Constrained decoding | outputs should be structurally unable to violate invariants | Lambda gates + deny-by-default surfaces; doctrine scanner as a hard CI gate (banned-token, Inv2) | FACT (CI-enforced) |
| 6 | Lean / TLA+ formal methods | claims of proof require machine-checkable artifacts | formula ledger (machine-checkable arithmetic); Lambda stays Conjecture 1 — never promoted to theorem by fiat | FACT (locked-8 immutable) |
| 7 | lm-evaluation-harness (EleutherAI) | evaluation is reproducible, versioned, and runnable by anyone | twelve-gate release receipts (schema frozen and hashed before results are viewed); frontier-bench repo | PROPOSAL (gates spec'd; checker implementation next) |
| 8 | HF Hub model cards / model-metadata conventions | a card is a contract; unsupported claims are violations | discovery scorecard + QUARANTINE.json for CARD_ONLY repos; "model-card claims equal receipts" is gate 12 | FACT (discovery + quarantine live) |
| 9 | RAGAS faithfulness / FActScore (atomic support) | long-form claims decompose into checkable atoms with evidence | braincite claim->source binding at claim granularity; citation coverage in brainverdict | FACT (live) |
| 10 | Graphiti bitemporal provenance (getzep) | every recalled fact carries (source, valid_time) | khipu receipts + provenance surfaces; brainprovenance lineage | PARTIAL (provenance live; bitemporality PROPOSAL) |

## Cross-cutting invariant (the estate's own)

Every leader pattern above reduces to one thing: **claims must be checkable by
someone who does not trust you.** The estate's recomposition of all ten is the
verifiable-answer receipt — question, sources, answer, honesty checks, signed
— which is why that primitive leads the frontier queue.

## Ablation discipline (program method)

None of the PROPOSAL/PARTIAL rows advance without: >= 3 seeds, frozen probe
sets, confidence intervals, and results published inconclusive if they are
inconclusive. Kept rows graduate to FACT with a receipt.
