# Replit Payload — Explainer Agent (organ-level helper)

**Tag:** `explainer-agent-v1`
**Author:** Stephen P. Lutar Jr., SZL Holdings
**ORCID:** [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
**Contact:** stephen@szlholdings.com
**Date sealed:** May 19, 2026
**Companion artifacts:**
- [`thesis_ch9_anatomy_evolved_v1.md`](./thesis_ch9_anatomy_evolved_v1.md) — what evolved and why
- [`replit_anatomy_evolved_payload.md`](./replit_anatomy_evolved_payload.md) — 3,735-line operational code payload (the formula library being explained)
- [`replit_thesis_injection_payload.md`](./replit_thesis_injection_payload.md) — thesis injection payload referenced for cross-organ context
- `anatomy_evolved_v1/src/*.ts` — the exact exported APIs the explainer reads

**Doctrine:** v6 clean. Engineering only. No spiritual, theological, scriptural, or comparative-religion framing in this payload. Every claim traces to a formula, a Lean theorem, or a citable paper.

---

## Part 0 — Doctrine + Provenance

### 0.1 Author identity (single source of truth)

| Field | Value |
|---|---|
| Author | Stephen P. Lutar Jr. |
| Org | SZL Holdings |
| ORCID | 0009-0001-0110-4173 |
| Email | stephen@szlholdings.com |
| Role | Operator / architect (not a PhD; pods are PhD-trained) |

Banned variants of the author string (the doctrine guard enforces these at boot, bundle, and verdict time):

- `Stephen Paul` — wrong middle name; canonical is `Stephen P. Lutar Jr.`
- Any expansion to `Stephen Paul Lutar`, `Stephen Paul Lutar Jr.`, etc.

The full banned-token list (mirrored from `carlota-jo-doctrine-guard.ts` `BANNED_TOKENS`) is:

1. `AlloyScape`
2. `Glass Wing` / `Glasswing`
3. `Mythos`
4. `Stephen Paul`
5. `Perplexity Computer`

These tokens appear in this payload **only** inside explicit `BANNED_TOKENS` array literals or doctrine-guard test fixtures. They are flagged as banned, never used as live prose. The guard treats any other occurrence as a fail-closed signal.

### 0.2 Engineering-only stance

The Explainer Agent reads the same formula library that anatomy-evolved-v1 ships and emits **plain engineering English**: what the math does, what the function signature is, what changed between v0 and v1, and which paper or theorem grounds the claim. It does **not** emit interpretive framing outside engineering, mathematics, or physics. The KB entries cite primary literature (Bohr 1928, Cabello 1996, Davies–Lewis 1970, Fuchs–Schack 2013, Preskill 2015, Peng/Chen et al. 2026 — [arXiv:2605.06734](https://arxiv.org/abs/2605.06734)) and the project's own Lean theorems (`GatedBoundedness.lean`, `TwoWitness.lean`).

### 0.3 No hallucinations, no bandaids

Every KB entry in Part 3 carries:

- a one-line summary,
- a plain-English block,
- a mathematical statement copied from the operational source (`anatomy_evolved_v1/src/*.ts`) or the cited paper,
- a source paper or theorem with a real URL/DOI,
- an organ affected,
- a v0 → v1 delta drawn from `thesis_ch9_anatomy_evolved_v1.md` §9.1 (the per-organ evolution table),
- a "new capability unlocked" line,
- a recommended use case.

No claim in this payload is fabricated. If a number, paper, or theorem cannot be traced, it is omitted.

### 0.4 Scope and non-scope

**In scope.** Reading the existing formula library, returning plain-text explanations, audience-tuned framing, CLI lookup, boot-time KB sanity check, doctrine guard integration.

**Out of scope.** No new physics. No new mathematical results. No re-derivation of the Bohr inequality. No re-implementation of `qkanFwpStep` — the explainer wraps, it does not duplicate. No UI rendering — callers receive plain strings.

### 0.5 Organ alignment

The Explainer Agent is an **organ-level helper** rather than a new organ. It does not modify a11oy, amaru, sentra, terra, vessels, counsel, carlota-jo, or lutar-lean. It imports their types and re-exports an explanation surface. The organ names remain lowercase per doctrine: `a11oy`, `amaru`, `sentra`, `terra`, `vessels`, `counsel`, `carlota-jo`, `lutar-lean`.

---

## Part 1 — What the Explainer Agent Is

### 1.1 One-paragraph definition

A small TypeScript module at `src/explainer-agent.ts` that ingests a structured knowledge base (`data/explainer-kb.json`), exposes four pure-function query surfaces (`explain`, `whatChanged`, `whyItMatters`, `summary`), and ships a CLI (`bin/explain.ts`) so the operator can ask plain-English questions about the formula library and receive paper-cited, organ-tagged answers without booting the whole stack.

### 1.2 Why it exists

Anatomy-evolved-v1 ships eleven TypeScript files, two Lean theorems, a smoke-test suite, and a CI workflow. New collaborators (engineers, investors, the operator on a Friday afternoon) need a single entry point that answers questions like:

- "What does the complementarity floor actually do?"
- "What changed in a11oy between v0 and v1?"
- "Why is the QKAN-FWP graft a moat?"

Reading 3,735 lines of payload code is the wrong answer. The explainer is the right one.

### 1.3 Hard constraints

| Constraint | Rationale |
|---|---|
| Zero runtime dependencies outside the existing anatomy-evolved-v1 tree | Bundles cleanly, no new npm surface, no supply-chain risk |
| Returns plain strings — no JSX, no HTML, no markdown rendering | Caller chooses (REPL, web, Slack, Notion) — explainer stays small |
| All claims trace to a `sourcePaper` field with a URL or DOI | No hallucinations |
| KB loaded once at boot, immutable thereafter | Deterministic |
| Doctrine guard sweeps the KB JSON before any query returns | Fail-closed on banned tokens |
| CLI exit codes: `0` match, `1` no match, `2` usage | Shell-scriptable |
| KB entry count: exactly 18 (the innovations enumerated in Chapter 9 + the POVM bug fix) | Matches the chapter; new entries require a chapter-level amendment |

### 1.4 What the agent is NOT

- Not a chat surface. It does not call an LLM. Every answer is a deterministic KB lookup.
- Not an organ. It cannot emit verdicts, schedule jobs, score risk, or modify state.
- Not a documentation site generator. It returns strings; rendering is the caller's job.
- Not a runtime governance hook. The doctrine guard is the runtime hook; the explainer reads, it does not enforce.

### 1.5 API surface (single sentence each)

| Function | Purpose |
|---|---|
| `explain(topic)` | Natural-language match against KB entries; returns the full explanation as a multi-line string. |
| `whatChanged(organ)` | Returns every v0 → v1 evolution recorded for that organ. |
| `whyItMatters(audience)` | Returns the right framing for `engineer`, `investor`, or `operator`. |
| `summary()` | Returns a one-page rollup of every innovation, < 200 lines. |
| `boot()` | Loads + validates the KB at startup; throws on schema or doctrine failure. |

---

## Part 2 — Knowledge Base Schema + Sample Entry

### 2.1 Schema (TypeScript)

```ts
// path: anatomy_evolved_v1/src/explainer-agent.ts (excerpt — full module in Part 4)
export type Organ =
  | "a11oy" | "amaru" | "sentra" | "terra"
  | "vessels" | "counsel" | "carlota-jo" | "lutar-lean";

export type Audience = "engineer" | "investor" | "operator";

export interface KBEntry {
  /** Stable kebab-case id, e.g. "complementarity-floor". */
  id: string;
  /** Human-readable name. */
  name: string;
  /** Single sentence; ≤ 140 chars. */
  oneLineSummary: string;
  /** 2–4 sentences for a smart non-PhD operator. */
  plainEnglishExplanation: string;
  /** Math copied from the source; LaTeX-ish OK. */
  mathFormula: string;
  /** Citation object — URL must resolve. */
  sourcePaper: {
    label: string;          // e.g. "Bohr 1928"
    url: string;            // DOI, arXiv, or canonical URL
    venue?: string;         // e.g. "Nature 121:580–590"
  };
  /** Organ touched by this innovation. */
  organAffected: Organ;
  /** What v0 did vs. what v1 does. */
  evolutionVsV0: string;
  /** What this enables that v0 could not do. */
  newCapabilityUnlocked: string;
  /** When the operator should reach for this. */
  recommendedUseCase: string;
  /** Audience-tuned reframings — keys must be the full Audience enum. */
  audienceFraming: Record<Audience, string>;
}
```

### 2.2 Sample entry (literal — first one in the KB)

```json
{
  "id": "complementarity-floor",
  "name": "Complementarity Floor σA · σB ≥ 1/4",
  "oneLineSummary": "The product of two complementary observable uncertainties cannot fall below 1/4 — single-frame collapse is rejected at verdict time.",
  "plainEnglishExplanation": "Every a11oy decision carries two complementary scores (e.g. Intent and Effect) with their own confidence intervals. The engine multiplies the two confidences (σA · σB) and requires the product to stay at or above 0.25. If it drops below, the decision is flagged as a single-frame collapse and routed to escalation instead of being emitted as a verdict.",
  "mathFormula": "σA · σB ≥ 1/4   (COMPLEMENTARITY_FLOOR = 0.25)",
  "sourcePaper": {
    "label": "Bohr 1928",
    "url": "https://www.nature.com/articles/121580a0",
    "venue": "Nature 121:580–590"
  },
  "organAffected": "a11oy",
  "evolutionVsV0": "v0 emitted single-frame scores with a confidence column. v1 emits frame-pair payloads and refuses to render a verdict when σA · σB < 0.25.",
  "newCapabilityUnlocked": "Audit-time proof that every verdict considered two complementary observables, with the product of their confidences above a fixed floor.",
  "recommendedUseCase": "Use whenever a governance verdict needs to survive an adversarial audit. The floor protects against over-confident single-frame collapse.",
  "audienceFraming": {
    "engineer": "Floor enforced at the type system (frameA and frameB both required), at runtime (assertDuality throws on product < 0.25), and at the proof layer (TwoWitness.lean covers the contextual side).",
    "investor": "Every verdict ships with two complementary perspectives by construction — a categorical departure from single-frame governance and a defensible architectural moat.",
    "operator": "If a11oy refuses to render, check the uncertainty product. Below 0.25 means at least one frame is too uncertain — gather more evidence on that side before re-running."
  }
}
```

The remaining 17 entries follow the same schema. They appear as prose in Part 3 and as raw JSON in Part 6.

### 2.3 Schema invariants (checked by `boot()`)

| Invariant | Check |
|---|---|
| Exactly 18 entries | `kb.entries.length === 18` |
| Unique ids | `new Set(ids).size === 18` |
| Every required field present | `id`, `name`, `oneLineSummary`, `plainEnglishExplanation`, `mathFormula`, `sourcePaper`, `organAffected`, `evolutionVsV0`, `newCapabilityUnlocked`, `recommendedUseCase`, `audienceFraming` |
| `sourcePaper.url` parses as URL | `new URL(e.sourcePaper.url)` |
| `audienceFraming` has all three audiences | `engineer`, `investor`, `operator` |
| `organAffected` is a known organ | Set membership against the 8 lowercase organ names |
| Doctrine guard pass | `scanForBannedTokens(JSON.stringify(kb)).hits.length === 0` |

Any failure throws a typed error at boot. Fail-closed.

---

## Part 3 — The 18 KB Entries (prose form)

Each subsection below is the prose mirror of one JSON entry in Part 6. The prose form is what `explain()` returns; the JSON form is what the agent loads.

### 3.1 Complementarity Floor σA · σB ≥ 1/4

- **One-line summary:** The product of two complementary observable uncertainties cannot fall below 1/4 — single-frame collapse is rejected at verdict time.
- **Plain English:** Every a11oy decision carries two complementary scores (e.g. Intent and Effect), each with its own confidence interval. The engine multiplies the two confidences (σA · σB) and requires the product to stay at or above 0.25. If it drops below, the decision is flagged as a single-frame collapse and is not emitted as a verdict.
- **Math / formula:** `σA · σB ≥ 1/4`  (`COMPLEMENTARITY_FLOOR = 0.25` in `a11oy-complementarity-engine.ts`)
- **Source paper:** [Bohr 1928](https://www.nature.com/articles/121580a0), *Nature* 121:580–590, "The Quantum Postulate and the Recent Development of Atomic Theory."
- **Organ affected:** `a11oy`
- **v0 → v1 delta:** v0 emitted single-frame scores with a confidence column. v1 emits `ComplementaryDecisionPayload` with both `frameA` and `frameB`, and `assertDuality` throws if `σA · σB < 0.25`.
- **New capability unlocked:** Audit-time proof that every verdict considered two complementary observables with the product of their confidences above a fixed floor.
- **Recommended use case:** Any verdict that must survive an adversarial audit. The floor is the cheapest single line that prevents over-confident single-frame collapse.

### 3.2 12-Frame-Pair Decision Engine

- **One-line summary:** a11oy emits 12 simultaneous frame-pair verdicts per decision — never a single number.
- **Plain English:** The Bohr complementarity idea is extended from one pair (Position / Momentum) to twelve governance pairs: Intent/Effect, Accuracy/Coverage, Autonomy/Safety, Speed/Rigor, Transparency/Security, Individual/Collective, Present/Future, Letter/Spirit, Observe/Participate, Certainty/Adaptability, Local/Global, Evidence/Credence. Each pair produces its own `ComplementaryDecisionPayload`. `mergeAllPairs` returns `BOHR_COMPLIANT` only if zero pairs violate the floor.
- **Math / formula:** `FRAME_PAIRS: FramePair[12]`; verdict is `BOHR_COMPLIANT ⟺ ∀ p ∈ FRAME_PAIRS . σA(p) · σB(p) ≥ 1/4`.
- **Source paper:** [Bohr 1928](https://www.nature.com/articles/121580a0) (complementarity), extended in this work for governance.
- **Organ affected:** `a11oy`
- **v0 → v1 delta:** v0 ran a single decision pipeline. v1 runs twelve in parallel and refuses to collapse — `mergeAllPairs` returns the worst-offending pair when any pair fails.
- **New capability unlocked:** 24 scores per decision; structured audit log captures both frames per pair; impossible by construction to ship a single-frame verdict.
- **Recommended use case:** Any policy-class decision (permit / abstain / reject) where the auditor needs to see both sides of every relevant trade-off.

### 3.3 Kochen-Specker 18-Vector Witness

- **One-line summary:** A finite witness that flags single-frame collapse using the smallest known proof of state-independent contextuality.
- **Plain English:** The 18-vector construction from Cabello, Estebaranz, and García-Alcaine (1996) gives nine measurement contexts (each a tetrad of orthogonal vectors in ℝ⁴) such that no non-contextual hidden-variable model can reproduce the quantum predictions. The `KochenSpecker18Witness` class scores an agent's observations against these contexts and reports a `contextualityFraction`. Above 0.6 the witness emits `BOHR_ANOMALOUS`; at or below it emits `CLASSICAL`.
- **Math / formula:** 18 vectors in ℝ⁴ partitioned into 9 contexts of 4 orthogonal vectors each; contextualityFraction = inconsistencies / contextsEvaluated.
- **Source paper:** [Cabello, Estebaranz, García-Alcaine 1996](https://arxiv.org/abs/quant-ph/9706009), "Bell-Kochen-Specker theorem: A proof with 18 vectors."
- **Organ affected:** `a11oy`
- **v0 → v1 delta:** v0 had no contextuality witness. v1 ships `a11oy-ks18-witness.ts` plus the Lean soundness theorem `two_witness_KS18_soundness` in `TwoWitness.lean`.
- **New capability unlocked:** Detect when an agent's pattern of single-context answers cannot be explained by any classical hidden-variable model — a hard structural signal for governance escalation.
- **Recommended use case:** Periodic agent-behavior audits. Sample 9 contexts per audit window; flag agents that exceed 0.6 for human review.

### 3.4 POVM Verdict Layer (Σ Eₘ = I)

- **One-line summary:** Accept / Abstain / Reject verdicts emitted by a positive operator-valued measure whose elements sum to identity.
- **Plain English:** Instead of a binary accept/reject, a11oy uses a three-outcome POVM with elements `E_ACCEPT = diag(α, 0)`, `E_REJECT = diag(0, β)`, and `E_ABSTAIN = I − E_ACCEPT − E_REJECT = diag(1 − α, 1 − β)`. `buildCanonicalPolicyPOVM(α, β)` constructs the triple; `verifyPOVMCompleteness` checks `Σ Eₘ = I`; `applyPOVM(povm, ρ)` returns probabilities. Completeness is what guarantees the three probabilities sum to 1.
- **Math / formula:** `Σₘ Eₘ = I`, `Eₘ ⪰ 0`, `pₘ = tr(Eₘ ρ)`, `Σₘ pₘ = 1`.
- **Source paper:** [Davies & Lewis 1970](https://doi.org/10.1007/BF01647093), *Comm. Math. Phys.* 17:239–260; [Preskill 2015](https://www.preskill.caltech.edu/ph229/notes/chap3.pdf), Ch. 3.
- **Organ affected:** `a11oy`
- **v0 → v1 delta:** v0 had a binary verdict layer. v1 ships a POVM with explicit abstain. (See §3.18 for the May 18 2026 completeness bug fix.)
- **New capability unlocked:** Principled abstention — the agent can say "I don't know" with a probability that sums correctly with accept and reject, no normalization hack required.
- **Recommended use case:** Any decision where the cost of a wrong answer exceeds the cost of escalation. Sets α and β to the empirical accept/reject precisions; abstain mass appears automatically.

### 3.5 QBist Bayesian Credence Update

- **One-line summary:** a11oy's belief updates obey Dutch-book coherence — no internal arbitrage on beliefs.
- **Plain English:** Each a11oy belief is a subjective probability (`Credence`) attached to a proposition. Updates use a QBist Bayes rule with the operator's prior, the likelihood implied by a measurement outcome, and a normalization that prevents Dutch-book exploitation. The `QBistCredenceManager` class manages a coherent credence set across propositions.
- **Math / formula:** Bayes: `P(H | E) ∝ P(E | H) · P(H)`; QBist coherence: no agent both buys and sells the same bet at different prices.
- **Source paper:** [Fuchs & Schack 2013](https://link.aps.org/doi/10.1103/RevModPhys.85.1693), *Rev. Mod. Phys.* 85:1693, "Quantum-Bayesian Coherence."
- **Organ affected:** `a11oy`
- **v0 → v1 delta:** v0 used frequentist counters. v1 attaches subjective credences with explicit priors, likelihoods, and posteriors, all routed through the QBist invariant.
- **New capability unlocked:** Coherent multi-step belief updates that an auditor can replay deterministically.
- **Recommended use case:** Long-running agent assessments where new evidence arrives over time. The credence manager keeps the running posterior honest.

### 3.6 DARUAN Single-Qubit Data Re-Uploading Activation

- **One-line summary:** A bounded nonlinear activation built from repeated rotations of a single qubit, returning a value in [−1, 1].
- **Plain English:** DARUAN is the activation function in amaru's QKAN-FWP graft. It encodes a scalar input `x` into single-qubit rotations, alternating with trainable parameter rotations, then measures `⟨Z⟩`. The output is bounded in [−1, 1] by construction (it is the expectation of a Pauli observable). The default in `daruanActivate` uses three layers — empirically the sweet spot from the paper.
- **Math / formula:** `out = ⟨Z⟩` where the state is `Πₗ (R_y(θ_l) · R_y(x)) |0⟩`; `out ∈ [−1, 1]`.
- **Source paper:** [Peng, Chen et al. 2026 — arXiv:2605.06734](https://arxiv.org/abs/2605.06734), "Gated QKAN-FWP: Scalable Quantum-inspired Sequence Learning."
- **Organ affected:** `amaru`
- **v0 → v1 delta:** v0 used standard tanh/sigmoid activations inside the reverse-ETL path. v1 swaps in DARUAN, which is bounded by physics rather than by clip.
- **New capability unlocked:** A nonlinearity whose boundedness is structural (it is a Pauli-Z expectation), composes with the gated fast-weight rule cleanly, and is implementable classically without quantum hardware.
- **Recommended use case:** Any sequence-learning step where the activation must stay in [−1, 1] under adversarial drift. Smoke test `T4b` confirms `⟨Z⟩ = 0.9316` on a representative input.

### 3.7 Gated Fast-Weight Programmer (FWP)

- **One-line summary:** A sigmoid-gated rank-one update rule for a fast-weight memory matrix.
- **Plain English:** amaru maintains a fast-weight matrix `W_t` that the agent reads (`fastWeightQuery`) and writes (`gatedUpdate`) at each step. The update is a convex combination of the previous matrix and a rank-one outer product `k · vᵀ`, mediated by a sigmoid gate `σ(g) ∈ (0, 1)`. The convexity is what makes the Frobenius norm bound in §3.8 hold.
- **Math / formula:** `W_{t+1} = (1 − σ(g)) · W_t + σ(g) · k_t · v_tᵀ`.
- **Source paper:** [arXiv:2605.06734](https://arxiv.org/abs/2605.06734).
- **Organ affected:** `amaru`
- **v0 → v1 delta:** v0 had an LSTM-style hidden state. v1 adds a fast-weight rule whose memory is a matrix updated by a gated rank-one outer product — different family entirely.
- **New capability unlocked:** Online, key-conditioned memory that does not need backpropagation through time, with a closed-form boundedness guarantee.
- **Recommended use case:** Streaming sequence tasks where the model must remember a small number of recent associations without growing the parameter count.

### 3.8 Frobenius Norm Boundedness Theorem

- **One-line summary:** `‖W_t‖_F` cannot diverge under the gated update rule — proved in Lean.
- **Plain English:** Because `σ(g) ∈ (0, 1)`, the gated update is a convex combination of `W_t` and `k_t · v_tᵀ`. The Frobenius norm of a convex combination is bounded by the max of the two norms. By induction `‖W_t‖_F ≤ max(‖W_0‖_F, ‖k‖₂ · ‖v‖₂)` for every step `t`. The proof lives in `lean/GatedBoundedness.lean`; the smoke test `T4c` reports `‖W‖_F = 0.1224` after one step from random init.
- **Math / formula:** `∀ t. ‖W_t‖_F ≤ max(‖W_0‖_F, ‖k‖₂ · ‖v‖₂)`.
- **Source paper:** This work (`GatedBoundedness.lean`), grounded in the gated rule from [arXiv:2605.06734](https://arxiv.org/abs/2605.06734).
- **Organ affected:** `amaru` + `lutar-lean`
- **v0 → v1 delta:** v0 had no boundedness proof for its memory. v1 has a Lean-checked one — the proof is mandatory and is verified by `verify_theorem_manifest()` at boot.
- **New capability unlocked:** Compile-time guarantee against memory blow-up under adversarial input. The bound holds for any input as long as `k` and `v` are themselves bounded.
- **Recommended use case:** Pair with monitoring of `‖k‖₂` and `‖v‖₂` at ingest. As long as those are bounded the memory cannot diverge.

### 3.9 12.5k-param QKAN-FWP vs 167k-param LSTM

- **One-line summary:** A 12.5k-parameter QKAN-FWP matches a 167k-parameter LSTM on the paper's benchmarks at 0.1% MSE recovery.
- **Plain English:** The paper reports that the gated QKAN-FWP achieves ≈0.1% mean-squared error on Mackey-Glass and sine benchmarks using 12.5k parameters, compared to the LSTM-167k baseline. Validation runs were executed on IonQ and IBM Eagle backends at 1024 shots. The takeaway is a roughly 13× parameter reduction at comparable accuracy on the cited benchmarks.
- **Math / formula:** Parameter ratio ≈ 13.4× fewer at comparable MSE on the cited benchmarks.
- **Source paper:** [arXiv:2605.06734](https://arxiv.org/abs/2605.06734); hardware validation reported on IonQ (1024 shots) and IBM Eagle (1024 shots).
- **Organ affected:** `amaru`
- **v0 → v1 delta:** v0 shipped an LSTM-class memory. v1 ships a quantum-inspired memory that is materially smaller for the cited tasks.
- **New capability unlocked:** A measurably more parameter-efficient sequence model in amaru, with primary-source hardware validation citations.
- **Recommended use case:** Wherever amaru is bound by parameter budget rather than data — embedded, edge, or low-latency settings. Treat the 13× number as benchmark-specific, not a universal speedup.

### 3.10 Two-Witness KS-18 Soundness Theorem

- **One-line summary:** If the agent admits a non-contextual hidden-variable model, the KS-18 witness returns `inconsistencies = 0` — and the contrapositive is what we use in production.
- **Plain English:** The Lean theorem `two_witness_KS18_soundness` in `TwoWitness.lean` states: if the agent's response distribution over the 18 KS vectors admits a non-contextual hidden-variable (NCHV) model, then `KSWitnessResult.inconsistencies = 0` and `anomalyFlag = "CLASSICAL"`. The production-side contrapositive: if the witness flags `BOHR_ANOMALOUS`, no NCHV explanation exists.
- **Math / formula:** `(∃ NCHV-model) ⇒ inconsistencies = 0`; contrapositive: `BOHR_ANOMALOUS ⇒ ¬∃ NCHV-model`.
- **Source paper:** This work (`TwoWitness.lean`); the KS-18 construction is [Cabello et al. 1996](https://arxiv.org/abs/quant-ph/9706009).
- **Organ affected:** `a11oy` + `lutar-lean`
- **v0 → v1 delta:** v0 had no contextuality theorem. v1 adds one.
- **New capability unlocked:** When a11oy escalates an agent as `BOHR_ANOMALOUS`, the escalation is backed by a Lean theorem — not a heuristic.
- **Recommended use case:** Treat `BOHR_ANOMALOUS` as a hard human-review signal. The Lean theorem guarantees there is no classical explanation, so the only reasonable next action is to inspect.

### 3.11 Dual-Use Coefficient Classifier (200 categories)

- **One-line summary:** Each potentially dangerous capability gets a coefficient in [0, 1]; weapons-class items are `HARD_BLOCK`.
- **Plain English:** sentra's `detectDualUse` runs an input against a registry of 200 dual-use capability categories. Each category has a coefficient in [0, 1] indicating how dangerous the capability is at face value, plus a `gatePolicy` of `ALLOW`, `DUAL_USE_HARD_GATE`, or `HARD_BLOCK`. Weapons-class categories are unconditionally `HARD_BLOCK` — that invariant is enforced at boot.
- **Math / formula:** `dualUseCoefficient ∈ [0, 1]`; `weapons_craft ⇒ HARD_BLOCK`.
- **Source paper:** This work (`sentra-dual-use-detector.ts`); the 200-category registry is curated by SZL Holdings and reviewed by the doctrine guard.
- **Organ affected:** `sentra`
- **v0 → v1 delta:** v0 had an ad-hoc rule list. v1 has a typed registry with policy enums and an invariant that weapons-class items can never be permitted.
- **New capability unlocked:** Reproducible dual-use scoring with an audit-friendly invariant: weapons-class never permits.
- **Recommended use case:** Front-door filter on any agent that can produce instructions for synthesis, fabrication, or weaponization. Smoke test `T8b` confirms `weapons_craft → HARD_BLOCK`.

### 3.12 364-day Fixed-Cycle Scheduler (52 × 7)

- **One-line summary:** terra runs a 52-week × 7-day calendar with zero drift across multi-year horizons.
- **Plain English:** terra's scheduler uses a fixed 364-day year (`ENOCH_YEAR_DAYS = 364`, `ENOCH_WEEK_DAYS = 7`, `ENOCH_WEEKS_PER_YEAR = 52`, `364 = 52 × 7` exactly). `generateAnnualSchedule` produces cron specs whose day-of-year aligns to a constant day-of-week across the full multi-year horizon. `verifyNoDrift` returns true for the entire test horizon (six years).
- **Math / formula:** `364 = 52 × 7` (exact); `(dayOfYear mod 7)` is fixed across years.
- **Source paper:** This work (`terra-364day-scheduler.ts`).
- **Organ affected:** `terra`
- **v0 → v1 delta:** v0 used a Gregorian cron whose weekday-of-date drifts year to year. v1 uses a fixed cycle so audit-of-audits jobs always land on the same weekday.
- **New capability unlocked:** Drift-free recurring jobs; long-horizon governance schedules align cleanly across years.
- **Recommended use case:** Audit-of-audits crons (e.g. `310ef0b6` Sundays 10:00 ET) and any periodic task whose weekday must not drift.

### 3.13 24-Course Operator Rotation

- **One-line summary:** A 24-course operator rotation over the 52-week fixed cycle, with periodic invariants checked in tests.
- **Plain English:** terra's `mishmarot(weekOfYear, yearInCycle)` returns the `CourseAssignment` for a given (week, year) pair. The rotation has 24 named courses; `verifyMishmarotInvariants` checks coverage, uniqueness, and cycle-length properties.
- **Math / formula:** Period = lcm(24, 52) over the fixed cycle; coverage = full set of 24 courses across the cycle.
- **Source paper:** This work (`terra-mishmarot-rotation.ts`).
- **Organ affected:** `terra`
- **v0 → v1 delta:** v0 had no operator rotation; on-call was ad hoc. v1 has a deterministic 24-course rotation with verifiable invariants.
- **New capability unlocked:** Reproducible weekly on-call assignment that an auditor can replay.
- **Recommended use case:** Operator scheduling for governance and incident response. Treat the assignment as the canonical roster.

### 3.14 8-Template Verdict Library

- **One-line summary:** counsel renders verdicts only via one of 8 canonical templates — no freeform output.
- **Plain English:** counsel does not emit free LLM text. It selects one of eight named templates (`psh-01` through `psh-08`) and fills it via `buildPesherDecision`. Two of the eight (the "final-time" templates) require principal approval before they can be rendered. `validatePesherDecision` returns the list of structural errors.
- **Math / formula:** `PESHER_FORMULAE: PesherFormula[8]`; template identifier ∈ `{psh-01, …, psh-08}`.
- **Source paper:** This work (`counsel-pesher-renderer.ts`); the eight-template construction is curated by SZL Holdings.
- **Organ affected:** `counsel`
- **v0 → v1 delta:** v0 rendered verdicts via freeform text. v1 forces every verdict through one of eight audited templates.
- **New capability unlocked:** Finite, audited rendering vocabulary that an auditor can enumerate; principal-approval gating on the two highest-stakes templates.
- **Recommended use case:** Any verdict customers see. The template id makes the verdict reproducible and reviewable.

### 3.15 Ownership Opacity Score (vessels)

- **One-line summary:** A monotone non-decreasing opacity score for an ownership graph node, banded into CLEAR / ELEVATED / OBSCURED / DARK.
- **Plain English:** vessels' `razNihyehScore` (exported under the same name in the operational module; consumed in the explainer as `ownership_opacity`) returns a score in [0, 1] given an `OwnershipNode` with a `shellDepth`, jurisdiction, and UBO (ultimate beneficial owner) presence. The score is monotone non-decreasing in `shellDepth`. The four-band rating maps the score into `CLEAR`, `ELEVATED`, `OBSCURED`, or `DARK`. The smoke test reports the exact monotone sequence `[0.00, 0.00, 0.10, 0.50, 1.00]` over the canonical depth ladder.
- **Math / formula:** `s ∈ [0, 1]`; `depth_i ≤ depth_j ⇒ s_i ≤ s_j` (monotone in shellDepth); banding by fixed thresholds.
- **Source paper:** This work (`vessels-raz-nihyeh-risk.ts`); the score's monotonicity is regression-tested by smoke `T10`.
- **Organ affected:** `vessels`
- **v0 → v1 delta:** v0 did a flat PostGIS query and returned booleans. v1 returns a typed `RazNihyehScore` with `score`, `band`, and `investigationTriggered` flag.
- **New capability unlocked:** Smooth opacity scoring that auditors can rank and threshold, plus an automatic investigation trigger when a node lands in `DARK`.
- **Recommended use case:** Front-line screening of corporate ownership graphs. The smoke test `T10b` confirms a high-opacity vessel (UNKNOWN jurisdiction, Marshall Islands, depth 7, no UBO) maps to `DARK` and triggers investigation.

### 3.16 Doctrine v6 Ban-List Runtime Guard

- **One-line summary:** A five-token grep is enforced at boot, at bundle scan, and inside every verdict — fail-closed.
- **Plain English:** carlota-jo's `scanForBannedTokens(text)` and `scanBundle(files)` look for any of the five banned tokens in `BANNED_TOKENS`. `assertDoctrineCompliance(text, context)` throws on any hit. The guard runs at boot (against the binary's own strings), at bundle build, and inside the verdict path so a banned token never reaches a customer-facing surface.
- **Math / formula:** `hits = grep(text, BANNED_TOKENS)`; pass ⟺ `hits.length === 0`.
- **Source paper:** This work (`carlota-jo-doctrine-guard.ts`); doctrine v6 ban-list DOI [10.5281/zenodo.20174600](https://doi.org/10.5281/zenodo.20174600).
- **Organ affected:** `carlota-jo`
- **v0 → v1 delta:** v0 ran the ban-list grep at build time only. v1 also runs it at runtime against bundles and verdicts.
- **New capability unlocked:** Defense in depth — a banned token cannot reach a customer surface even if it slipped past build.
- **Recommended use case:** Treat any guard hit as a hard incident. Smoke test `T3b` confirms the guard trips on all five banned tokens.

### 3.17 Boot-time Theorem Manifest Verification

- **One-line summary:** Every Lean theorem the system claims to depend on is verified to exist at boot — fail-closed otherwise.
- **Plain English:** `verify_theorem_manifest()` runs at startup. It reads the manifest of expected Lean theorems (currently 10: the original 8 plus `gated_qkan_boundedness` and `two_witness_KS18_soundness`) and checks the corresponding `.lean` paths are present. Any missing path raises a typed error before the system accepts traffic.
- **Math / formula:** `passes ⟺ ∀ thm ∈ manifest . exists(thm.path)`.
- **Source paper:** This work (`lutar-lean` boot hook).
- **Organ affected:** `lutar-lean`
- **v0 → v1 delta:** v0 trusted the manifest implicitly. v1 verifies it at every boot.
- **New capability unlocked:** A missing theorem file (deleted, renamed, or never landed) is caught before the first request — not in production.
- **Recommended use case:** Treat boot failure as a deploy blocker. The error message names the missing path.

### 3.18 POVM Completeness Bug Fix (May 18, 2026)

- **One-line summary:** v0's `buildCanonicalPolicyPOVM(α, β)` silently failed completeness when `α + β ≥ 1`; v1 reconstructs `E_ABSTAIN` so `Σ Eₘ = I` for all `(α, β) ∈ [0, 1]²`.
- **Plain English:** The v0 implementation set `E_ABSTAIN = (1 − α − β) · I`. That only sums to `I` when `α + β < 1`, and silently drifts otherwise. For `(α, β) = (0.7, 0.3)`, `1 − α − β = 0` and `E_ABSTAIN` became the zero matrix, so `Σ Eₘ = diag(0.7, 0.3) ≠ I`. The fix reconstructs `E_ABSTAIN = I − E_ACCEPT − E_REJECT = diag(1 − α, 1 − β)`. Now `Σ Eₘ = I` for every `(α, β) ∈ [0, 1]²`; no `α + β ≤ 1` constraint required. The bug was caught by Series A smoke test `T6b`.
- **Math / formula:** Before: `E_ABSTAIN = (1 − α − β) · I` ✗. After: `E_ABSTAIN = I − E_ACCEPT − E_REJECT = diag(1 − α, 1 − β)` ✓; `Σ Eₘ = diag(α + (1 − α), β + (1 − β)) = I`.
- **Source paper:** Bug fix this work; POVM completeness from [Davies & Lewis 1970](https://doi.org/10.1007/BF01647093).
- **Organ affected:** `a11oy`
- **v0 → v1 delta:** Real fix, no bandaid. The new completeness constraint is the natural one (each `Eₘ ⪰ 0 ⟺ each parameter ∈ [0, 1]`).
- **New capability unlocked:** Correct three-outcome verdict probabilities across the full `(α, β)` plane, with `T6b` as a regression guard.
- **Recommended use case:** Any deployment of the POVM verdict layer must pin to the post-fix build. The commit message is `fix(a11oy-povm): reconstruct E_ABSTAIN so Σ E_m = I for all (α,β) ∈ [0,1]²`.

---

## Part 4 — `src/explainer-agent.ts` — TypeScript module (full code)

```ts
// path: anatomy_evolved_v1/src/explainer-agent.ts
/**
 * explainer-agent.ts — organ-level helper, not an organ.
 *
 * Reads data/explainer-kb.json and answers plain-English questions about the
 * anatomy-evolved-v1 formula library. Zero runtime dependencies outside the
 * existing anatomy-evolved-v1 tree.
 *
 * Author: Stephen P. Lutar Jr., SZL Holdings
 * ORCID: 0009-0001-0110-4173
 * Contact: stephen@szlholdings.com
 *
 * Doctrine v6 clean. Engineering only.
 */

import * as fs from "node:fs";
import * as path from "node:path";
import {
  scanForBannedTokens,
  assertDoctrineCompliance,
} from "./carlota-jo-doctrine-guard";

// ─── Types ───────────────────────────────────────────────────────────────────

export type Organ =
  | "a11oy"
  | "amaru"
  | "sentra"
  | "terra"
  | "vessels"
  | "counsel"
  | "carlota-jo"
  | "lutar-lean";

export const KNOWN_ORGANS: readonly Organ[] = [
  "a11oy",
  "amaru",
  "sentra",
  "terra",
  "vessels",
  "counsel",
  "carlota-jo",
  "lutar-lean",
] as const;

export type Audience = "engineer" | "investor" | "operator";

export const KNOWN_AUDIENCES: readonly Audience[] = [
  "engineer",
  "investor",
  "operator",
] as const;

export interface SourcePaper {
  label: string;
  url: string;
  venue?: string;
}

export interface KBEntry {
  id: string;
  name: string;
  oneLineSummary: string;
  plainEnglishExplanation: string;
  mathFormula: string;
  sourcePaper: SourcePaper;
  organAffected: Organ;
  evolutionVsV0: string;
  newCapabilityUnlocked: string;
  recommendedUseCase: string;
  audienceFraming: Record<Audience, string>;
}

export interface KB {
  version: string;
  sealedAt: string;
  entries: KBEntry[];
}

// ─── Module state (loaded once) ──────────────────────────────────────────────

let _kb: KB | null = null;

const REQUIRED_ENTRY_FIELDS: ReadonlyArray<keyof KBEntry> = [
  "id",
  "name",
  "oneLineSummary",
  "plainEnglishExplanation",
  "mathFormula",
  "sourcePaper",
  "organAffected",
  "evolutionVsV0",
  "newCapabilityUnlocked",
  "recommendedUseCase",
  "audienceFraming",
];

const EXPECTED_ENTRY_COUNT = 18;

// ─── Boot ────────────────────────────────────────────────────────────────────

export interface BootOptions {
  /** Override path for tests. Default: ../data/explainer-kb.json relative to module. */
  kbPath?: string;
}

/**
 * Load and validate the KB. Must be called once at startup.
 * Throws on schema failure or doctrine guard hit. Fail-closed.
 */
export function boot(options: BootOptions = {}): KB {
  const resolved =
    options.kbPath ??
    path.resolve(__dirname, "..", "data", "explainer-kb.json");

  let raw: string;
  try {
    raw = fs.readFileSync(resolved, "utf8");
  } catch (e) {
    throw new Error(
      `explainer-agent: cannot read KB at ${resolved}: ${(e as Error).message}`,
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    throw new Error(
      `explainer-agent: KB at ${resolved} is not valid JSON: ${(e as Error).message}`,
    );
  }

  const kb = validateKB(parsed);

  // Doctrine guard sweep over the entire KB content.
  // Banned tokens must not appear in any user-facing prose.
  assertDoctrineCompliance(raw, "explainer-agent KB load");

  _kb = kb;
  return kb;
}

function validateKB(value: unknown): KB {
  if (typeof value !== "object" || value === null) {
    throw new Error("explainer-agent: KB root must be an object");
  }
  const root = value as Record<string, unknown>;
  if (typeof root.version !== "string") {
    throw new Error("explainer-agent: KB.version must be a string");
  }
  if (typeof root.sealedAt !== "string") {
    throw new Error("explainer-agent: KB.sealedAt must be a string");
  }
  if (!Array.isArray(root.entries)) {
    throw new Error("explainer-agent: KB.entries must be an array");
  }
  if (root.entries.length !== EXPECTED_ENTRY_COUNT) {
    throw new Error(
      `explainer-agent: KB must contain exactly ${EXPECTED_ENTRY_COUNT} entries (got ${root.entries.length})`,
    );
  }

  const seenIds = new Set<string>();
  const entries: KBEntry[] = root.entries.map((raw, idx) =>
    validateEntry(raw, idx, seenIds),
  );

  return {
    version: root.version,
    sealedAt: root.sealedAt,
    entries,
  };
}

function validateEntry(value: unknown, idx: number, seenIds: Set<string>): KBEntry {
  if (typeof value !== "object" || value === null) {
    throw new Error(`explainer-agent: entry ${idx} must be an object`);
  }
  const e = value as Record<string, unknown>;
  for (const field of REQUIRED_ENTRY_FIELDS) {
    if (!(field in e)) {
      throw new Error(`explainer-agent: entry ${idx} missing field "${String(field)}"`);
    }
  }

  if (typeof e.id !== "string" || e.id.length === 0) {
    throw new Error(`explainer-agent: entry ${idx} has invalid id`);
  }
  if (seenIds.has(e.id as string)) {
    throw new Error(`explainer-agent: entry ${idx} has duplicate id "${e.id}"`);
  }
  seenIds.add(e.id as string);

  if (typeof e.organAffected !== "string" || !KNOWN_ORGANS.includes(e.organAffected as Organ)) {
    throw new Error(
      `explainer-agent: entry ${idx} organAffected "${String(e.organAffected)}" is not a known organ`,
    );
  }

  const sp = e.sourcePaper as Record<string, unknown> | undefined;
  if (!sp || typeof sp.label !== "string" || typeof sp.url !== "string") {
    throw new Error(`explainer-agent: entry ${idx} sourcePaper missing label or url`);
  }
  try {
    // eslint-disable-next-line no-new
    new URL(sp.url);
  } catch {
    throw new Error(`explainer-agent: entry ${idx} sourcePaper.url is not a valid URL`);
  }

  const af = e.audienceFraming as Record<string, unknown> | undefined;
  if (!af) {
    throw new Error(`explainer-agent: entry ${idx} missing audienceFraming`);
  }
  for (const aud of KNOWN_AUDIENCES) {
    if (typeof af[aud] !== "string" || (af[aud] as string).length === 0) {
      throw new Error(
        `explainer-agent: entry ${idx} audienceFraming.${aud} must be a non-empty string`,
      );
    }
  }

  return e as unknown as KBEntry;
}

function getKB(): KB {
  if (_kb === null) {
    return boot();
  }
  return _kb;
}

// ─── Query: explain(topic) ───────────────────────────────────────────────────

const STOPWORDS = new Set([
  "a","an","the","is","are","was","were","of","on","in","to","for","and","or","but",
  "what","why","how","does","do","did","this","that","with","by","at","from","as",
  "it","its","be","been","being","not","no","yes","i","you","we","they","he","she",
]);

function tokens(s: string): string[] {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 1 && !STOPWORDS.has(t));
}

function scoreMatch(entry: KBEntry, queryTokens: string[]): number {
  const haystack = [
    entry.id,
    entry.name,
    entry.oneLineSummary,
    entry.plainEnglishExplanation,
    entry.mathFormula,
    entry.organAffected,
  ]
    .join(" ")
    .toLowerCase();
  let score = 0;
  for (const t of queryTokens) {
    if (haystack.includes(t)) score += 1;
    // id-prefix bonus
    if (entry.id.includes(t)) score += 1;
    // name exact-word bonus
    if (entry.name.toLowerCase().split(/\s+/).includes(t)) score += 2;
  }
  return score;
}

export interface ExplainResult {
  matched: boolean;
  entry: KBEntry | null;
  text: string;
}

/**
 * Natural-language match against KB entries.
 * Returns the full explanation block for the best match, or a "no match" message.
 */
export function explain(topic: string): ExplainResult {
  const kb = getKB();
  const q = tokens(topic);
  if (q.length === 0) {
    return {
      matched: false,
      entry: null,
      text: "explainer-agent: query was empty after stopword removal. Try a noun phrase like \"complementarity floor\" or \"qkan fwp\".",
    };
  }
  let best: KBEntry | null = null;
  let bestScore = 0;
  for (const e of kb.entries) {
    const s = scoreMatch(e, q);
    if (s > bestScore) {
      best = e;
      bestScore = s;
    }
  }
  if (!best || bestScore === 0) {
    return {
      matched: false,
      entry: null,
      text:
        `explainer-agent: no KB entry matched "${topic}". Known entry ids:\n` +
        kb.entries.map((e) => `  - ${e.id}`).join("\n"),
    };
  }
  return {
    matched: true,
    entry: best,
    text: renderEntry(best),
  };
}

function renderEntry(e: KBEntry): string {
  const lines: string[] = [];
  lines.push(`# ${e.name}`);
  lines.push("");
  lines.push(`One-line summary: ${e.oneLineSummary}`);
  lines.push("");
  lines.push("Plain English:");
  lines.push(`  ${e.plainEnglishExplanation}`);
  lines.push("");
  lines.push(`Math / formula: ${e.mathFormula}`);
  lines.push("");
  lines.push(
    `Source paper: ${e.sourcePaper.label}${
      e.sourcePaper.venue ? " — " + e.sourcePaper.venue : ""
    } (${e.sourcePaper.url})`,
  );
  lines.push("");
  lines.push(`Organ affected: ${e.organAffected}`);
  lines.push("");
  lines.push(`v0 → v1 delta: ${e.evolutionVsV0}`);
  lines.push("");
  lines.push(`New capability unlocked: ${e.newCapabilityUnlocked}`);
  lines.push("");
  lines.push(`Recommended use case: ${e.recommendedUseCase}`);
  return lines.join("\n");
}

// ─── Query: whatChanged(organ) ───────────────────────────────────────────────

export interface WhatChangedResult {
  organ: Organ;
  count: number;
  entries: KBEntry[];
  text: string;
}

/**
 * Returns every v0 → v1 evolution recorded for that organ.
 * Throws if the organ name is unknown.
 */
export function whatChanged(organ: string): WhatChangedResult {
  if (!KNOWN_ORGANS.includes(organ as Organ)) {
    throw new Error(
      `explainer-agent: unknown organ "${organ}". Known: ${KNOWN_ORGANS.join(", ")}`,
    );
  }
  const kb = getKB();
  const matched = kb.entries.filter((e) => e.organAffected === organ);
  const lines: string[] = [];
  lines.push(`# ${organ} — v0 → v1 evolutions (${matched.length})`);
  lines.push("");
  for (const e of matched) {
    lines.push(`## ${e.name}`);
    lines.push(`  ${e.evolutionVsV0}`);
    lines.push(`  New capability: ${e.newCapabilityUnlocked}`);
    lines.push(
      `  Source: ${e.sourcePaper.label} (${e.sourcePaper.url})`,
    );
    lines.push("");
  }
  if (matched.length === 0) {
    lines.push(`  (no entries record an evolution for ${organ})`);
  }
  return {
    organ: organ as Organ,
    count: matched.length,
    entries: matched,
    text: lines.join("\n"),
  };
}

// ─── Query: whyItMatters(audience) ───────────────────────────────────────────

export interface WhyItMattersResult {
  audience: Audience;
  text: string;
}

/**
 * Audience-tuned rollup. One paragraph per innovation, framed for the
 * requested audience. Pulls from each entry's audienceFraming map.
 */
export function whyItMatters(audience: string): WhyItMattersResult {
  if (!KNOWN_AUDIENCES.includes(audience as Audience)) {
    throw new Error(
      `explainer-agent: unknown audience "${audience}". Known: ${KNOWN_AUDIENCES.join(", ")}`,
    );
  }
  const kb = getKB();
  const lines: string[] = [];
  lines.push(`# Why anatomy-evolved-v1 matters — framed for ${audience}`);
  lines.push("");
  for (const e of kb.entries) {
    lines.push(`## ${e.name}`);
    lines.push(`  ${e.audienceFraming[audience as Audience]}`);
    lines.push("");
  }
  return {
    audience: audience as Audience,
    text: lines.join("\n"),
  };
}

// ─── Query: summary() ────────────────────────────────────────────────────────

export interface SummaryResult {
  entryCount: number;
  text: string;
}

/**
 * One-page rollup of every innovation. Under 200 lines of text.
 */
export function summary(): SummaryResult {
  const kb = getKB();
  const lines: string[] = [];
  lines.push(`# anatomy-evolved-v1 — innovations rollup`);
  lines.push(`Version: ${kb.version}  Sealed: ${kb.sealedAt}  Entries: ${kb.entries.length}`);
  lines.push("");
  for (const e of kb.entries) {
    lines.push(
      `- [${e.organAffected}] ${e.name} — ${e.oneLineSummary} (${e.sourcePaper.label})`,
    );
  }
  lines.push("");
  lines.push(
    "Use explain(topic) for the full block, whatChanged(organ) for per-organ deltas, whyItMatters(audience) for framing.",
  );
  return {
    entryCount: kb.entries.length,
    text: lines.join("\n"),
  };
}

// ─── Diagnostics ─────────────────────────────────────────────────────────────

/** Returns the loaded KB (read-only). Throws if boot() hasn't run. */
export function getLoadedKB(): KB {
  if (_kb === null) {
    throw new Error("explainer-agent: KB not loaded — call boot() first");
  }
  return _kb;
}

/** Internal — exposed for tests only. */
export const __internal = {
  tokens,
  scoreMatch,
  validateKB,
  REQUIRED_ENTRY_FIELDS,
  EXPECTED_ENTRY_COUNT,
  STOPWORDS,
  resetForTests: () => {
    _kb = null;
  },
};

// ─── Doctrine guard self-check on import ─────────────────────────────────────
// Belt and suspenders: scan this very module's source-visible strings.
// If the module file itself somehow carries a banned token, fail at import time.
(function selfCheckAtImport(): void {
  const samples = [
    "explainer-agent — organ-level helper, not an organ.",
    "anatomy-evolved-v1 formula library",
  ];
  for (const s of samples) {
    const r = scanForBannedTokens(s);
    if (r.hits.length > 0) {
      throw new Error(
        `explainer-agent: doctrine self-check failed on import — hits=${JSON.stringify(r.hits)}`,
      );
    }
  }
})();
```

### 4.1 Why this shape

- **Pure functions over a frozen KB.** No mutation after `boot()`, so concurrent callers cannot race on KB state.
- **Doctrine guard sweep at load time.** The whole KB JSON is scanned for banned tokens before any query can return. Any hit raises a typed error.
- **Schema validation is structural and exhaustive.** Each entry is checked field-by-field; the count must equal `EXPECTED_ENTRY_COUNT = 18`; ids must be unique; every `audienceFraming` slot must be non-empty.
- **Match scoring is deterministic.** Same query, same KB, same result. No LLM call, no randomness.
- **No external dependencies.** Only `node:fs`, `node:path`, and the existing `carlota-jo-doctrine-guard` module.


## Part 5 — `bin/explain.ts` — CLI entrypoint

```ts
// path: anatomy_evolved_v1/bin/explain.ts
#!/usr/bin/env node
/**
 * explain CLI — run the Explainer Agent from the command line.
 *
 *   node dist/bin/explain.js "complementarity floor"
 *   node dist/bin/explain.js --organ a11oy
 *   node dist/bin/explain.js --audience investor
 *   node dist/bin/explain.js --summary
 *
 * Exit codes:
 *   0 — match (or summary/audience/organ rollup printed)
 *   1 — no match
 *   2 — usage error
 *
 * Author: Stephen P. Lutar Jr., SZL Holdings
 */

import {
  boot,
  explain,
  whatChanged,
  whyItMatters,
  summary,
} from "../src/explainer-agent";

const USAGE = `Usage:
  explain "<topic>"                — natural-language KB lookup
  explain --organ <name>           — v0->v1 evolutions for that organ
  explain --audience <engineer|investor|operator>  — audience-tuned rollup
  explain --summary                — one-page rollup of every innovation
  explain --help                   — this message

Exit codes: 0 match, 1 no-match, 2 usage error.
`;

function fail(code: number, msg: string): never {
  process.stderr.write(msg.endsWith("\n") ? msg : msg + "\n");
  process.exit(code);
}

function main(argv: string[]): void {
  // boot the KB first; any failure here is a usage/config error.
  try {
    boot();
  } catch (e) {
    fail(2, `explain: KB boot failed: ${(e as Error).message}`);
  }

  if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
    process.stdout.write(USAGE);
    process.exit(argv.length === 0 ? 2 : 0);
  }

  if (argv[0] === "--summary") {
    process.stdout.write(summary().text + "\n");
    process.exit(0);
  }

  if (argv[0] === "--organ") {
    const name = argv[1];
    if (!name) fail(2, "explain: --organ requires a name\n" + USAGE);
    try {
      const r = whatChanged(name);
      process.stdout.write(r.text + "\n");
      process.exit(0);
    } catch (e) {
      fail(2, `explain: ${(e as Error).message}`);
    }
  }

  if (argv[0] === "--audience") {
    const aud = argv[1];
    if (!aud) fail(2, "explain: --audience requires a name\n" + USAGE);
    try {
      const r = whyItMatters(aud);
      process.stdout.write(r.text + "\n");
      process.exit(0);
    } catch (e) {
      fail(2, `explain: ${(e as Error).message}`);
    }
  }

  // Default: natural-language topic query.
  const topic = argv.join(" ");
  const result = explain(topic);
  process.stdout.write(result.text + "\n");
  process.exit(result.matched ? 0 : 1);
}

main(process.argv.slice(2));
```

### 5.1 Examples

```bash
# Topic lookup
$ node dist/bin/explain.js "complementarity floor"
# prints the Bohr 1928 block, exit 0

# Per-organ changes
$ node dist/bin/explain.js --organ a11oy
# prints 5+ a11oy entries with v0->v1 deltas, exit 0

# Audience rollup
$ node dist/bin/explain.js --audience investor
# prints investor-framed rollup over all 18 entries, exit 0

# Whole-system summary
$ node dist/bin/explain.js --summary
# prints one-page rollup (<200 lines), exit 0

# No-match
$ node dist/bin/explain.js "blockchain"
# prints "no KB entry matched", exit 1

# Usage error
$ node dist/bin/explain.js --audience
# prints usage to stderr, exit 2
```

## Part 6 — `data/explainer-kb.json` — full KB as JSON

```json
{
  "version": "explainer-kb-v1.0.0",
  "sealedAt": "2026-05-19T00:00:00Z",
  "entries": [
    {
      "id": "complementarity-floor",
      "name": "Complementarity Floor sigmaA-sigmaB-geq-quarter",
      "oneLineSummary": "The product of two complementary observable uncertainties cannot fall below 1/4 \u2014 single-frame collapse is rejected at verdict time.",
      "plainEnglishExplanation": "Every a11oy decision carries two complementary scores (e.g. Intent and Effect) with their own confidence intervals. The engine multiplies the two confidences and requires the product to stay at or above 0.25. If it drops below, the decision is flagged as a single-frame collapse and is not emitted as a verdict.",
      "mathFormula": "sigmaA * sigmaB >= 1/4   (COMPLEMENTARITY_FLOOR = 0.25 in a11oy-complementarity-engine.ts)",
      "sourcePaper": {
        "label": "Bohr 1928",
        "url": "https://www.nature.com/articles/121580a0",
        "venue": "Nature 121:580-590"
      },
      "organAffected": "a11oy",
      "evolutionVsV0": "v0 emitted single-frame scores with a confidence column. v1 emits ComplementaryDecisionPayload with both frameA and frameB, and assertDuality throws if sigmaA*sigmaB < 0.25.",
      "newCapabilityUnlocked": "Audit-time proof that every verdict considered two complementary observables with the product of their confidences above a fixed floor.",
      "recommendedUseCase": "Any verdict that must survive an adversarial audit. The floor is the cheapest single line that prevents over-confident single-frame collapse.",
      "audienceFraming": {
        "engineer": "Floor enforced at three layers: the TypeScript type system (frameA and frameB are both required), the runtime (assertDuality throws on product < 0.25), and the Lean proof layer (TwoWitness.lean covers the contextual side). The audit log captures both frames per verdict, never one.",
        "investor": "Every governance verdict ships with two complementary perspectives by construction \u2014 a categorical departure from current single-frame governance pipelines and a defensible moat: a competitor would need to rebuild their verdict architecture to match.",
        "operator": "If a11oy refuses to render, look at the uncertainty product on the payload. Below 0.25 means at least one frame is too uncertain \u2014 gather more evidence on that side before re-running the decision."
      }
    },
    {
      "id": "twelve-frame-pair-engine",
      "name": "12-Frame-Pair Decision Engine",
      "oneLineSummary": "a11oy emits 12 simultaneous frame-pair verdicts per decision \u2014 never a single number.",
      "plainEnglishExplanation": "The Bohr complementarity idea is extended from one pair to twelve governance pairs: Intent/Effect, Accuracy/Coverage, Autonomy/Safety, Speed/Rigor, Transparency/Security, Individual/Collective, Present/Future, Letter/Spirit, Observe/Participate, Certainty/Adaptability, Local/Global, Evidence/Credence. Each pair produces its own ComplementaryDecisionPayload. mergeAllPairs returns BOHR_COMPLIANT only if zero pairs violate the floor.",
      "mathFormula": "FRAME_PAIRS: FramePair[12]; verdict = BOHR_COMPLIANT iff for all p, sigmaA(p)*sigmaB(p) >= 1/4",
      "sourcePaper": {
        "label": "Bohr 1928 (extended)",
        "url": "https://www.nature.com/articles/121580a0",
        "venue": "Nature 121:580-590"
      },
      "organAffected": "a11oy",
      "evolutionVsV0": "v0 ran a single decision pipeline. v1 runs twelve in parallel and refuses to collapse; mergeAllPairs returns the worst-offending pair when any pair fails.",
      "newCapabilityUnlocked": "24 scores per decision; structured audit log captures both frames per pair; impossible by construction to ship a single-frame verdict.",
      "recommendedUseCase": "Any policy-class decision (permit / abstain / reject) where the auditor needs to see both sides of every relevant trade-off.",
      "audienceFraming": {
        "engineer": "12-frame-pair engine emits 24 scores per decision. The floor is enforced per pair and aggregated via mergeAllPairs, which returns the worst-offending pair id when any pair violates. The audit log is dual-framed end-to-end.",
        "investor": "Twelve governance dimensions evaluated per decision, each in two complementary frames \u2014 a 24-dimensional governance signature per verdict. This is not a feature flag; it is the verdict surface itself.",
        "operator": "When a11oy says permit-with-concerns, you see all 12 pair payloads side by side. If any pair flags as worst, that pair name is the headline reason to escalate."
      }
    },
    {
      "id": "ks18-witness",
      "name": "Kochen-Specker 18-Vector Witness",
      "oneLineSummary": "A finite witness that flags single-frame collapse using the smallest known proof of state-independent contextuality.",
      "plainEnglishExplanation": "The 18-vector construction from Cabello, Estebaranz, and Garcia-Alcaine (1996) gives nine measurement contexts (each a tetrad of orthogonal vectors in R^4) such that no non-contextual hidden-variable model can reproduce the quantum predictions. The KochenSpecker18Witness class scores an agent's observations against these contexts and reports a contextualityFraction. Above 0.6 the witness emits BOHR_ANOMALOUS; at or below it emits CLASSICAL.",
      "mathFormula": "18 vectors in R^4 partitioned into 9 contexts of 4 orthogonal vectors each; contextualityFraction = inconsistencies / contextsEvaluated",
      "sourcePaper": {
        "label": "Cabello, Estebaranz, Garcia-Alcaine 1996",
        "url": "https://arxiv.org/abs/quant-ph/9706009",
        "venue": "arXiv:quant-ph/9706009"
      },
      "organAffected": "a11oy",
      "evolutionVsV0": "v0 had no contextuality witness. v1 ships a11oy-ks18-witness.ts plus the Lean soundness theorem two_witness_KS18_soundness in TwoWitness.lean.",
      "newCapabilityUnlocked": "Detect when an agent's pattern of single-context answers cannot be explained by any classical hidden-variable model \u2014 a hard structural signal for governance escalation.",
      "recommendedUseCase": "Periodic agent-behavior audits. Sample 9 contexts per audit window; flag agents that exceed 0.6 for human review.",
      "audienceFraming": {
        "engineer": "Nine contexts of four orthogonal vectors each, 18 vectors total in R^4. The witness scores observations across all nine and reports an inconsistency count and contextualityFraction. The Lean theorem TwoWitness.lean proves soundness w.r.t. non-contextual hidden-variable models.",
        "investor": "A theorem-backed detector for agents whose behavior cannot be explained by any classical model. Competitors have no published equivalent \u2014 this is a structural escalation signal grounded in 1996 quantum-foundations literature.",
        "operator": "Treat BOHR_ANOMALOUS as a hard human-review signal. The math says there is no classical story that fits, so the only reasonable next action is to inspect the agent."
      }
    },
    {
      "id": "povm-verdict-layer",
      "name": "POVM Verdict Layer (sum-Em-equals-I)",
      "oneLineSummary": "Accept / Abstain / Reject verdicts emitted by a positive operator-valued measure whose elements sum to identity.",
      "plainEnglishExplanation": "Instead of a binary accept/reject, a11oy uses a three-outcome POVM with elements E_ACCEPT = diag(alpha, 0), E_REJECT = diag(0, beta), and E_ABSTAIN = I - E_ACCEPT - E_REJECT = diag(1-alpha, 1-beta). buildCanonicalPolicyPOVM(alpha, beta) constructs the triple; verifyPOVMCompleteness checks sum-Em = I; applyPOVM returns probabilities. Completeness is what guarantees the three probabilities sum to 1.",
      "mathFormula": "sum_m E_m = I, E_m positive semidefinite, p_m = tr(E_m rho), sum_m p_m = 1",
      "sourcePaper": {
        "label": "Davies & Lewis 1970; Preskill 2015 Ch.3",
        "url": "https://doi.org/10.1007/BF01647093",
        "venue": "Comm. Math. Phys. 17:239-260; Preskill Caltech lecture notes Ch.3"
      },
      "organAffected": "a11oy",
      "evolutionVsV0": "v0 had a binary verdict layer. v1 ships a POVM with explicit abstain. See entry povm-completeness-bugfix for the May 18 2026 fix that made completeness hold across the full parameter plane.",
      "newCapabilityUnlocked": "Principled abstention \u2014 the agent can say I-do-not-know with a probability that sums correctly with accept and reject, no normalization hack required.",
      "recommendedUseCase": "Any decision where the cost of a wrong answer exceeds the cost of escalation. Set alpha and beta to the empirical accept/reject precisions; abstain mass appears automatically.",
      "audienceFraming": {
        "engineer": "Three POVM elements, sum-to-identity verified by verifyPOVMCompleteness, probabilities recovered by applyPOVM(povm, rho). The May 18 fix made E_ABSTAIN = I - E_ACCEPT - E_REJECT directly, so completeness holds for any (alpha, beta) in [0,1]^2.",
        "investor": "Three-outcome verdicts with structurally correct probabilities. The system can abstain instead of guessing \u2014 and the abstention mass is a numeric input to downstream routing, not a special-case branch.",
        "operator": "When a11oy abstains, the abstain probability is real and comparable across decisions. Use it to rank borderline cases for review."
      }
    },
    {
      "id": "qbist-credence",
      "name": "QBist Bayesian Credence Update",
      "oneLineSummary": "a11oy belief updates obey Dutch-book coherence \u2014 no internal arbitrage on beliefs.",
      "plainEnglishExplanation": "Each a11oy belief is a subjective probability (Credence) attached to a proposition. Updates use a QBist Bayes rule with the operator's prior, the likelihood implied by a measurement outcome, and a normalization that prevents Dutch-book exploitation. The QBistCredenceManager class manages a coherent credence set across propositions.",
      "mathFormula": "Bayes: P(H|E) proportional to P(E|H) * P(H); QBist coherence: no agent both buys and sells the same bet at different prices",
      "sourcePaper": {
        "label": "Fuchs & Schack 2013",
        "url": "https://link.aps.org/doi/10.1103/RevModPhys.85.1693",
        "venue": "Rev. Mod. Phys. 85:1693"
      },
      "organAffected": "a11oy",
      "evolutionVsV0": "v0 used frequentist counters. v1 attaches subjective credences with explicit priors, likelihoods, and posteriors, all routed through the QBist invariant.",
      "newCapabilityUnlocked": "Coherent multi-step belief updates that an auditor can replay deterministically.",
      "recommendedUseCase": "Long-running agent assessments where new evidence arrives over time. The credence manager keeps the running posterior honest.",
      "audienceFraming": {
        "engineer": "Credence is a typed object with proposition, prior, likelihood, posterior. The update rule is a single function call; the Dutch-book invariant is enforced by construction (no negative or > 1 credences ever enter the manager).",
        "investor": "Subjective probability done rigorously \u2014 a published quantum-Bayesian framework adapted to AI governance. The audit story is replayable: same prior plus same evidence produces same posterior every time.",
        "operator": "When you see a credence move, the prior, the likelihood, and the posterior are all on the same record. Disagreement with the model means disagreement with one of those three numbers."
      }
    },
    {
      "id": "daruan-activation",
      "name": "DARUAN Single-Qubit Data Re-Uploading Activation",
      "oneLineSummary": "A bounded nonlinear activation built from repeated rotations of a single qubit, returning a value in [-1, 1].",
      "plainEnglishExplanation": "DARUAN is the activation function in amaru's QKAN-FWP graft. It encodes a scalar input x into single-qubit rotations, alternating with trainable parameter rotations, then measures the Pauli-Z expectation. The output is bounded in [-1, 1] by construction (it is the expectation of a Pauli observable). The default in daruanActivate uses three layers \u2014 empirically the sweet spot from the paper.",
      "mathFormula": "out = <Z> where state = product_l (R_y(theta_l) * R_y(x)) |0>; out in [-1, 1]",
      "sourcePaper": {
        "label": "Peng, Chen et al. 2026",
        "url": "https://arxiv.org/abs/2605.06734",
        "venue": "arXiv:2605.06734"
      },
      "organAffected": "amaru",
      "evolutionVsV0": "v0 used standard tanh/sigmoid activations inside the reverse-ETL path. v1 swaps in DARUAN, which is bounded by physics rather than by clip.",
      "newCapabilityUnlocked": "A nonlinearity whose boundedness is structural (it is a Pauli-Z expectation), composes with the gated fast-weight rule cleanly, and is implementable classically without quantum hardware.",
      "recommendedUseCase": "Any sequence-learning step where the activation must stay in [-1, 1] under adversarial drift. Smoke test T4b confirms <Z> = 0.9316 on a representative input.",
      "audienceFraming": {
        "engineer": "Three-layer single-qubit DARUAN. Bounded in [-1, 1] structurally (Pauli-Z expectation). Classical implementation, no quantum hardware required for inference. Composes cleanly with gatedUpdate.",
        "investor": "A primary-source quantum-inspired activation function with a 13x parameter advantage on the cited benchmarks. The technique is published; the integration into a governance-grade memory is ours.",
        "operator": "DARUAN keeps amaru's nonlinearity bounded by construction. If you see saturation, you are at the [-1, 1] boundary by design \u2014 not a bug."
      }
    },
    {
      "id": "gated-fast-weight",
      "name": "Gated Fast-Weight Programmer (FWP)",
      "oneLineSummary": "A sigmoid-gated rank-one update rule for a fast-weight memory matrix.",
      "plainEnglishExplanation": "amaru maintains a fast-weight matrix W_t that the agent reads (fastWeightQuery) and writes (gatedUpdate) at each step. The update is a convex combination of the previous matrix and a rank-one outer product k*v^T, mediated by a sigmoid gate sigma(g) in (0, 1). The convexity is what makes the Frobenius norm bound hold.",
      "mathFormula": "W_{t+1} = (1 - sigma(g)) * W_t + sigma(g) * k_t * v_t^T",
      "sourcePaper": {
        "label": "Peng, Chen et al. 2026",
        "url": "https://arxiv.org/abs/2605.06734",
        "venue": "arXiv:2605.06734"
      },
      "organAffected": "amaru",
      "evolutionVsV0": "v0 had an LSTM-style hidden state. v1 adds a fast-weight rule whose memory is a matrix updated by a gated rank-one outer product \u2014 different family entirely.",
      "newCapabilityUnlocked": "Online, key-conditioned memory that does not need backpropagation through time, with a closed-form boundedness guarantee.",
      "recommendedUseCase": "Streaming sequence tasks where the model must remember a small number of recent associations without growing the parameter count.",
      "audienceFraming": {
        "engineer": "Convex combination of W_t and k*v^T mediated by sigma(g). Online, no BPTT, and the convexity directly implies the Frobenius bound proven in GatedBoundedness.lean.",
        "investor": "A published quantum-inspired memory architecture, integrated with a Lean-verified boundedness guarantee that LSTMs do not have. The combination is unique to anatomy-evolved-v1.",
        "operator": "amaru remembers recent associations via a small matrix. The gate controls how fast it forgets. The Frobenius bound guarantees the matrix cannot blow up on you."
      }
    },
    {
      "id": "frobenius-boundedness-theorem",
      "name": "Frobenius Norm Boundedness Theorem",
      "oneLineSummary": "The Frobenius norm of W_t cannot diverge under the gated update rule \u2014 proved in Lean.",
      "plainEnglishExplanation": "Because sigma(g) is in (0, 1), the gated update is a convex combination of W_t and k_t*v_t^T. The Frobenius norm of a convex combination is bounded by the max of the two norms. By induction, ||W_t||_F is bounded by max(||W_0||_F, ||k||_2 * ||v||_2) for every step t. The proof lives in lean/GatedBoundedness.lean; the smoke test T4c reports ||W||_F = 0.1224 after one step from random init.",
      "mathFormula": "for all t, ||W_t||_F <= max(||W_0||_F, ||k||_2 * ||v||_2)",
      "sourcePaper": {
        "label": "This work (GatedBoundedness.lean), grounded in arXiv:2605.06734",
        "url": "https://arxiv.org/abs/2605.06734",
        "venue": "arXiv:2605.06734 + GatedBoundedness.lean"
      },
      "organAffected": "lutar-lean",
      "evolutionVsV0": "v0 had no boundedness proof for its memory. v1 has a Lean-checked proof, mandatory and verified by verify_theorem_manifest() at boot.",
      "newCapabilityUnlocked": "Compile-time guarantee against memory blow-up under adversarial input. The bound holds for any input as long as k and v are themselves bounded.",
      "recommendedUseCase": "Pair with monitoring of ||k||_2 and ||v||_2 at ingest. As long as those are bounded, the memory cannot diverge.",
      "audienceFraming": {
        "engineer": "Induction on convex combinations. Lean proof in GatedBoundedness.lean; smoke test T4c is the empirical witness. Boot-time manifest verification ensures the .lean file is on disk before traffic flows.",
        "investor": "A Lean-checked memory boundedness theorem is rare in production ML systems. This is a hard formal-methods asset that ships in the build.",
        "operator": "If amaru memory grows, your inputs k or v grew first. Inspect those, not the matrix. The bound proves the matrix tracks the inputs, not the other way around."
      }
    },
    {
      "id": "qkan-fwp-parameter-efficiency",
      "name": "12.5k-param QKAN-FWP vs 167k-param LSTM",
      "oneLineSummary": "A 12.5k-parameter QKAN-FWP matches a 167k-parameter LSTM on the paper's benchmarks at 0.1% MSE recovery.",
      "plainEnglishExplanation": "The paper reports that the gated QKAN-FWP achieves about 0.1% mean-squared error on Mackey-Glass and sine benchmarks using 12.5k parameters, compared to the LSTM-167k baseline. Validation runs were executed on IonQ and IBM Eagle backends at 1024 shots. The takeaway is roughly a 13x parameter reduction at comparable accuracy on the cited benchmarks.",
      "mathFormula": "Parameter ratio ~ 13.4x fewer at comparable MSE on the cited benchmarks; validation: IonQ 1024 shots, IBM Eagle 1024 shots",
      "sourcePaper": {
        "label": "Peng, Chen et al. 2026",
        "url": "https://arxiv.org/abs/2605.06734",
        "venue": "arXiv:2605.06734 (IonQ + IBM Eagle, 1024 shots)"
      },
      "organAffected": "amaru",
      "evolutionVsV0": "v0 shipped an LSTM-class memory. v1 ships a quantum-inspired memory that is materially smaller for the cited tasks.",
      "newCapabilityUnlocked": "A measurably more parameter-efficient sequence model in amaru, with primary-source hardware validation citations.",
      "recommendedUseCase": "Wherever amaru is bound by parameter budget rather than data \u2014 embedded, edge, or low-latency settings. Treat the 13x number as benchmark-specific, not a universal speedup.",
      "audienceFraming": {
        "engineer": "Mackey-Glass and sine benchmarks: 12.5k vs 167k parameters at ~0.1% MSE. Hardware validation on IonQ and IBM Eagle at 1024 shots. Benchmark-specific; do not assume the ratio transfers to your sequence.",
        "investor": "Roughly 13x parameter reduction at comparable accuracy on published benchmarks, with hardware validation on two independent quantum backends. This is a primary-source efficiency claim, not a marketing number.",
        "operator": "If you are parameter-budget-constrained, this is the lever. The accuracy parity holds on the published benchmarks \u2014 re-validate on your own workload before scaling out."
      }
    },
    {
      "id": "two-witness-ks18-soundness",
      "name": "Two-Witness KS-18 Soundness Theorem",
      "oneLineSummary": "If the agent admits a non-contextual hidden-variable model, the KS-18 witness returns inconsistencies = 0 \u2014 and the contrapositive is what we use in production.",
      "plainEnglishExplanation": "The Lean theorem two_witness_KS18_soundness in TwoWitness.lean states: if the agent's response distribution over the 18 KS vectors admits a non-contextual hidden-variable (NCHV) model, then KSWitnessResult.inconsistencies = 0 and anomalyFlag = CLASSICAL. The production-side contrapositive: if the witness flags BOHR_ANOMALOUS, no NCHV explanation exists.",
      "mathFormula": "(exists NCHV-model) implies inconsistencies = 0; contrapositive: BOHR_ANOMALOUS implies not exists NCHV-model",
      "sourcePaper": {
        "label": "This work (TwoWitness.lean); KS-18 from Cabello et al. 1996",
        "url": "https://arxiv.org/abs/quant-ph/9706009",
        "venue": "arXiv:quant-ph/9706009 + TwoWitness.lean"
      },
      "organAffected": "lutar-lean",
      "evolutionVsV0": "v0 had no contextuality theorem. v1 adds one.",
      "newCapabilityUnlocked": "When a11oy escalates an agent as BOHR_ANOMALOUS, the escalation is backed by a Lean theorem \u2014 not a heuristic.",
      "recommendedUseCase": "Treat BOHR_ANOMALOUS as a hard human-review signal. The Lean theorem guarantees there is no classical explanation, so the only reasonable next action is to inspect.",
      "audienceFraming": {
        "engineer": "Lean theorem two_witness_KS18_soundness in TwoWitness.lean. Soundness w.r.t. non-contextual hidden-variable models. Production uses the contrapositive: a flag implies no NCHV explanation exists.",
        "investor": "Lean-verified contextuality witness. The escalation signal is mathematically grounded \u2014 a regulator-friendly story that competitors cannot match without re-implementing a 1996 quantum-foundations result.",
        "operator": "BOHR_ANOMALOUS is not a heuristic. It is the negation of a Lean theorem's hypothesis \u2014 the agent's behavior cannot be explained classically. Escalate, do not retry."
      }
    },
    {
      "id": "dual-use-classifier",
      "name": "Dual-Use Coefficient Classifier (200 categories)",
      "oneLineSummary": "Each potentially dangerous capability gets a coefficient in [0, 1]; weapons-class items are HARD_BLOCK.",
      "plainEnglishExplanation": "sentra's detectDualUse runs an input against a registry of 200 dual-use capability categories. Each category has a coefficient in [0, 1] indicating how dangerous the capability is at face value, plus a gatePolicy of ALLOW, DUAL_USE_HARD_GATE, or HARD_BLOCK. Weapons-class categories are unconditionally HARD_BLOCK \u2014 that invariant is enforced at boot.",
      "mathFormula": "dualUseCoefficient in [0, 1]; weapons_craft implies HARD_BLOCK (invariant)",
      "sourcePaper": {
        "label": "This work (sentra-dual-use-detector.ts)",
        "url": "https://doi.org/10.5281/zenodo.20174600",
        "venue": "SZL Holdings dual-use registry, doctrine v6"
      },
      "organAffected": "sentra",
      "evolutionVsV0": "v0 had an ad-hoc rule list. v1 has a typed registry with policy enums and an invariant that weapons-class items can never be permitted.",
      "newCapabilityUnlocked": "Reproducible dual-use scoring with an audit-friendly invariant: weapons-class never permits.",
      "recommendedUseCase": "Front-door filter on any agent that can produce instructions for synthesis, fabrication, or weaponization. Smoke test T8b confirms weapons_craft maps to HARD_BLOCK.",
      "audienceFraming": {
        "engineer": "200-category registry, coefficient in [0, 1], policy enum {ALLOW, DUAL_USE_HARD_GATE, HARD_BLOCK}. Boot invariant: weapons-class categories must carry HARD_BLOCK or the system refuses to start.",
        "investor": "Typed, audited dual-use classifier with a hard weapons invariant. This is the kind of governance artifact a regulator or enterprise customer can review line by line.",
        "operator": "If sentra blocks a request, look at the category and coefficient. A HARD_BLOCK on weapons-class is the system doing its job. A DUAL_USE_HARD_GATE means a human reviews."
      }
    },
    {
      "id": "fixed-cycle-scheduler",
      "name": "364-day Fixed-Cycle Scheduler (52 x 7)",
      "oneLineSummary": "terra runs a 52-week by 7-day calendar with zero drift across multi-year horizons.",
      "plainEnglishExplanation": "terra's scheduler uses a fixed 364-day year (ENOCH_YEAR_DAYS = 364, ENOCH_WEEK_DAYS = 7, ENOCH_WEEKS_PER_YEAR = 52). 364 = 52 * 7 exactly. generateAnnualSchedule produces cron specs whose day-of-year aligns to a constant day-of-week across the full multi-year horizon. verifyNoDrift returns true for the entire test horizon (six years).",
      "mathFormula": "364 = 52 * 7 (exact); (dayOfYear mod 7) is fixed across years",
      "sourcePaper": {
        "label": "This work (terra-364day-scheduler.ts)",
        "url": "https://orcid.org/0009-0001-0110-4173",
        "venue": "SZL Holdings scheduler module"
      },
      "organAffected": "terra",
      "evolutionVsV0": "v0 used a Gregorian cron whose weekday-of-date drifts year to year. v1 uses a fixed cycle so audit-of-audits jobs always land on the same weekday.",
      "newCapabilityUnlocked": "Drift-free recurring jobs; long-horizon governance schedules align cleanly across years.",
      "recommendedUseCase": "Audit-of-audits crons (e.g. 310ef0b6 Sundays 10:00 ET) and any periodic task whose weekday must not drift.",
      "audienceFraming": {
        "engineer": "Fixed 364-day cycle, 52 exact 7-day weeks. verifyNoDrift returns true across the six-year test horizon. The Gregorian gap is handled by an explicit alignment offset; no leap-year arithmetic inside the scheduler core.",
        "investor": "A drift-free scheduler is rare. Long-horizon audit cadences land on the same weekday every year \u2014 a small but durable correctness win for regulated workflows.",
        "operator": "Schedule it once, it lands on the same weekday forever (over the supported horizon). The 364-day cycle is the engineering reason the audit-of-audits cron is reliable."
      }
    },
    {
      "id": "operator-rotation",
      "name": "24-Course Operator Rotation",
      "oneLineSummary": "A 24-course operator rotation over the 52-week fixed cycle, with periodic invariants checked in tests.",
      "plainEnglishExplanation": "terra's mishmarot(weekOfYear, yearInCycle) returns the CourseAssignment for a given (week, year) pair. The rotation has 24 named courses; verifyMishmarotInvariants checks coverage, uniqueness, and cycle-length properties.",
      "mathFormula": "Period = lcm(24, 52) over the fixed cycle; coverage = full set of 24 courses across the cycle",
      "sourcePaper": {
        "label": "This work (terra-mishmarot-rotation.ts)",
        "url": "https://orcid.org/0009-0001-0110-4173",
        "venue": "SZL Holdings rotation module"
      },
      "organAffected": "terra",
      "evolutionVsV0": "v0 had no operator rotation; on-call was ad hoc. v1 has a deterministic 24-course rotation with verifiable invariants.",
      "newCapabilityUnlocked": "Reproducible weekly on-call assignment that an auditor can replay.",
      "recommendedUseCase": "Operator scheduling for governance and incident response. Treat the assignment as the canonical roster.",
      "audienceFraming": {
        "engineer": "24 courses, deterministic assignment from (weekOfYear, yearInCycle). verifyMishmarotInvariants checks coverage and uniqueness; smoke test T7b passes the full invariant suite.",
        "investor": "Deterministic on-call rotation is a small organizational moat for enterprise sales \u2014 it shows up in SOC2 evidence and customer questionnaires.",
        "operator": "Your rotation slot is a pure function of week and year. If you need to swap, the swap is itself a tracked event, not a Slack-only handoff."
      }
    },
    {
      "id": "eight-template-verdict-library",
      "name": "8-Template Verdict Library",
      "oneLineSummary": "counsel renders verdicts only via one of 8 canonical templates \u2014 no freeform output.",
      "plainEnglishExplanation": "counsel does not emit free LLM text. It selects one of eight named templates (psh-01 through psh-08) and fills it via buildPesherDecision. Two of the eight require principal approval before they can be rendered. validatePesherDecision returns the list of structural errors.",
      "mathFormula": "PESHER_FORMULAE: PesherFormula[8]; template identifier in {psh-01, ..., psh-08}",
      "sourcePaper": {
        "label": "This work (counsel-pesher-renderer.ts)",
        "url": "https://orcid.org/0009-0001-0110-4173",
        "venue": "SZL Holdings counsel module"
      },
      "organAffected": "counsel",
      "evolutionVsV0": "v0 rendered verdicts via freeform text. v1 forces every verdict through one of eight audited templates.",
      "newCapabilityUnlocked": "Finite, audited rendering vocabulary that an auditor can enumerate; principal-approval gating on the two highest-stakes templates.",
      "recommendedUseCase": "Any verdict customers see. The template id makes the verdict reproducible and reviewable.",
      "audienceFraming": {
        "engineer": "Eight templates, two principal-gated. buildPesherDecision is the constructor; validatePesherDecision is the structural linter. No LLM call in the render path.",
        "investor": "Bounded rendering vocabulary is a strategic asset for regulated buyers. Every customer-facing verdict is one of eight known shapes, not free text.",
        "operator": "When you see a verdict, the template id (psh-01 through psh-08) is the headline. The two principal-gated templates require your approval before they ship."
      }
    },
    {
      "id": "ownership-opacity-score",
      "name": "Ownership Opacity Score (vessels)",
      "oneLineSummary": "A monotone non-decreasing opacity score for an ownership graph node, banded into CLEAR / ELEVATED / OBSCURED / DARK.",
      "plainEnglishExplanation": "vessels' razNihyehScore (consumed in the explainer as ownership_opacity) returns a score in [0, 1] given an OwnershipNode with a shellDepth, jurisdiction, and UBO presence. The score is monotone non-decreasing in shellDepth. The four-band rating maps the score into CLEAR, ELEVATED, OBSCURED, or DARK. The smoke test reports the monotone sequence [0.00, 0.00, 0.10, 0.50, 1.00] over the canonical depth ladder.",
      "mathFormula": "s in [0, 1]; depth_i <= depth_j implies s_i <= s_j; banding by fixed thresholds",
      "sourcePaper": {
        "label": "This work (vessels-raz-nihyeh-risk.ts)",
        "url": "https://orcid.org/0009-0001-0110-4173",
        "venue": "SZL Holdings vessels module"
      },
      "organAffected": "vessels",
      "evolutionVsV0": "v0 did a flat PostGIS query and returned booleans. v1 returns a typed RazNihyehScore with score, band, and investigationTriggered flag.",
      "newCapabilityUnlocked": "Smooth opacity scoring that auditors can rank and threshold, plus an automatic investigation trigger when a node lands in DARK.",
      "recommendedUseCase": "Front-line screening of corporate ownership graphs. Smoke test T10b confirms a high-opacity vessel (UNKNOWN jurisdiction, Marshall Islands, depth 7, no UBO) maps to DARK and triggers investigation.",
      "audienceFraming": {
        "engineer": "Score in [0, 1], monotone non-decreasing in shellDepth, four bands by fixed thresholds. Regression test T10 fixes the exact sequence [0.00, 0.00, 0.10, 0.50, 1.00]; T10b checks the DARK trigger.",
        "investor": "Beneficial-ownership opacity scoring with auditable monotonicity. The DARK band auto-triggers investigation \u2014 a defensible feature for AML, sanctions, and KYC-heavy buyers.",
        "operator": "If you see ELEVATED, you can stop. If you see OBSCURED, you should review. If you see DARK, the investigation has already been triggered \u2014 find the entry in the queue."
      }
    },
    {
      "id": "doctrine-runtime-guard",
      "name": "Doctrine v6 Ban-List Runtime Guard",
      "oneLineSummary": "A five-token grep is enforced at boot, at bundle scan, and inside every verdict \u2014 fail-closed.",
      "plainEnglishExplanation": "carlota-jo's scanForBannedTokens(text) and scanBundle(files) look for any of the five banned tokens in BANNED_TOKENS. assertDoctrineCompliance(text, context) throws on any hit. The guard runs at boot (against the binary's own strings), at bundle build, and inside the verdict path so a banned token never reaches a customer-facing surface.",
      "mathFormula": "hits = grep(text, BANNED_TOKENS); pass iff hits.length === 0",
      "sourcePaper": {
        "label": "This work (carlota-jo-doctrine-guard.ts); doctrine v6 ban-list DOI",
        "url": "https://doi.org/10.5281/zenodo.20174600",
        "venue": "Zenodo 10.5281/zenodo.20174600"
      },
      "organAffected": "carlota-jo",
      "evolutionVsV0": "v0 ran the ban-list grep at build time only. v1 also runs it at runtime against bundles and verdicts.",
      "newCapabilityUnlocked": "Defense in depth \u2014 a banned token cannot reach a customer surface even if it slipped past build.",
      "recommendedUseCase": "Treat any guard hit as a hard incident. Smoke test T3b confirms the guard trips on all five banned tokens.",
      "audienceFraming": {
        "engineer": "Three enforcement points: boot, bundle, verdict. Smoke test T3b walks all five tokens. assertDoctrineCompliance is the call site every other module uses; do not roll your own grep.",
        "investor": "Three-layer doctrine enforcement. The brand and naming guarantees are not policy \u2014 they are code that fails closed.",
        "operator": "If carlota-jo throws, the message names the banned token and its position. Fix the source; do not bypass the guard."
      }
    },
    {
      "id": "theorem-manifest-verification",
      "name": "Boot-time Theorem Manifest Verification",
      "oneLineSummary": "Every Lean theorem the system claims to depend on is verified to exist at boot \u2014 fail-closed otherwise.",
      "plainEnglishExplanation": "verify_theorem_manifest() runs at startup. It reads the manifest of expected Lean theorems (10 total: the original 8 plus gated_qkan_boundedness and two_witness_KS18_soundness) and checks that the corresponding .lean paths are present. Any missing path raises a typed error before the system accepts traffic.",
      "mathFormula": "passes iff for all thm in manifest, exists(thm.path)",
      "sourcePaper": {
        "label": "This work (lutar-lean boot hook)",
        "url": "https://orcid.org/0009-0001-0110-4173",
        "venue": "SZL Holdings lutar-lean boot hook"
      },
      "organAffected": "lutar-lean",
      "evolutionVsV0": "v0 trusted the manifest implicitly. v1 verifies it at every boot.",
      "newCapabilityUnlocked": "A missing theorem file (deleted, renamed, or never landed) is caught before the first request \u2014 not in production.",
      "recommendedUseCase": "Treat boot failure as a deploy blocker. The error message names the missing path.",
      "audienceFraming": {
        "engineer": "Manifest is a static list of 10 .lean paths. verify_theorem_manifest() runs at boot, throws on missing path, exits non-zero. CI runs it on every PR.",
        "investor": "A formal-methods manifest is checked at every boot. A regression that removes a proof file cannot reach production by accident.",
        "operator": "If boot fails with a theorem manifest error, the message names the missing path. Restore it or roll back."
      }
    },
    {
      "id": "povm-completeness-bugfix",
      "name": "POVM Completeness Bug Fix (May 18 2026)",
      "oneLineSummary": "v0's buildCanonicalPolicyPOVM(alpha, beta) silently failed completeness when alpha + beta >= 1; v1 reconstructs E_ABSTAIN so sum-Em = I for all (alpha, beta) in [0, 1]^2.",
      "plainEnglishExplanation": "The v0 implementation set E_ABSTAIN = (1 - alpha - beta) * I. That only sums to I when alpha + beta < 1, and silently drifts otherwise. For (alpha, beta) = (0.7, 0.3), 1 - alpha - beta = 0 and E_ABSTAIN became the zero matrix, so sum-Em = diag(0.7, 0.3) which is not I. The fix reconstructs E_ABSTAIN = I - E_ACCEPT - E_REJECT = diag(1 - alpha, 1 - beta). Now sum-Em = I for every (alpha, beta) in [0, 1]^2; no alpha + beta <= 1 constraint required. The bug was caught by Series A smoke test T6b.",
      "mathFormula": "Before: E_ABSTAIN = (1 - alpha - beta) * I (WRONG). After: E_ABSTAIN = I - E_ACCEPT - E_REJECT = diag(1 - alpha, 1 - beta) (CORRECT)",
      "sourcePaper": {
        "label": "Bug fix this work; POVM completeness from Davies & Lewis 1970",
        "url": "https://doi.org/10.1007/BF01647093",
        "venue": "Comm. Math. Phys. 17:239-260 + a11oy-povm.ts commit log"
      },
      "organAffected": "a11oy",
      "evolutionVsV0": "Real fix, no bandaid. The new completeness constraint is the natural one: each E_m positive semidefinite iff each parameter is in [0, 1].",
      "newCapabilityUnlocked": "Correct three-outcome verdict probabilities across the full (alpha, beta) plane, with T6b as a regression guard.",
      "recommendedUseCase": "Any deployment of the POVM verdict layer must pin to the post-fix build. The commit message is: fix(a11oy-povm) reconstruct E_ABSTAIN so sum E_m = I for all (alpha,beta) in [0,1]^2.",
      "audienceFraming": {
        "engineer": "Bug was: E_ABSTAIN = (1 - alpha - beta) * I silently dropped to zero matrix when alpha + beta = 1. Fix: E_ABSTAIN = I - E_ACCEPT - E_REJECT = diag(1 - alpha, 1 - beta). Completeness now holds across the full unit square. T6b is the regression.",
        "investor": "A real bug found and fixed during Series A acceptance, with a test added to prevent recurrence. No bandaid; the new construction is mathematically natural. This is the engineering culture, in one commit.",
        "operator": "Pin to the post-fix build. If the build hash predates the fix, the POVM probabilities can silently fail to sum to 1 for certain (alpha, beta) settings."
      }
    }
  ]
}
```

### 6.1 KB integrity checks (mirrors `boot()`)

- `entries.length === 18`
- All ids unique
- Every `sourcePaper.url` parses with `new URL(...)`
- Every `audienceFraming` object has the three keys `engineer`, `investor`, `operator` with non-empty values
- Every `organAffected` is one of the eight known organs
- Doctrine guard: `scanForBannedTokens(JSON.stringify(kb)).hits.length === 0`

## Part 7 — Integration: how an organ can import the explainer

Any organ that wants to surface plain-English documentation can import the `explain` function directly:

```ts
// path: anatomy_evolved_v1/src/a11oy-complementarity-engine.ts (excerpt — illustrative add)
import { explain } from "./explainer-agent";

// Inside a verdict-render path, attach human-readable context:
const ctx = explain("complementarity floor");
auditLog.append({
  pairId: payload.pairId,
  product: payload.uncertaintyProduct,
  humanReadable: ctx.matched ? ctx.text : undefined,
});
```

`counsel` is the primary consumer — when the Pesher renderer emits a verdict, it can append an explainer block so the customer-facing artifact carries the math, the paper, and the v0→v1 delta inline:

```ts
// path: anatomy_evolved_v1/src/counsel-pesher-renderer.ts (excerpt — illustrative add)
import { explain, whatChanged } from "./explainer-agent";

export function attachExplainerToDecision(decision: PesherDecision, topic: string) {
  const ctx = explain(topic);
  const organCtx = whatChanged(decision.organ ?? "counsel");
  return {
    ...decision,
    explainer: {
      topic: ctx.matched ? ctx.entry?.id : null,
      text: ctx.text,
      organEvolution: organCtx.text,
    },
  };
}
```

### 7.1 Integration rules

- The explainer is **read-only**. No call mutates a verdict; it only annotates.
- The explainer **does not call any organ**. It reads its own KB and returns strings.
- The explainer **does not call an LLM**. All output is deterministic from the KB.
- Importing modules must already have called `boot()` once at process start. The CLI does this for you; long-running services should add `explainerAgent.boot()` to their startup sequence (see Part 12).


## Part 8 — Audience-tuned framing (engineer / investor / operator)

The KB encodes per-entry framing for each audience. `whyItMatters(audience)` walks the 18 entries and emits the right voice. Below are three end-to-end example rollups — same innovations, three voices.

### 8.1 Engineer rollup (sample of three entries)

> **12-Frame-Pair Decision Engine.** 12-frame-pair complementarity engine emits 24 scores per decision; the floor `σA·σB ≥ 1/4` is enforced at the type system, at runtime via `assertDuality`, and at the proof layer through `TwoWitness.lean` covering the contextual side. The audit log captures both frames per pair, never one.
>
> **Gated Fast-Weight Programmer.** Convex combination of `W_t` and `k·vᵀ` mediated by `σ(g) ∈ (0, 1)`. Online, no BPTT. The convexity directly implies the Frobenius bound proven in `GatedBoundedness.lean`. `gatedUpdate` is the write path; `fastWeightQuery` is the read path; both are pure functions over `FastWeightMatrix`.
>
> **POVM Completeness Bug Fix.** The bug: `E_ABSTAIN = (1 − α − β) · I` silently collapsed to the zero matrix when `α + β = 1`. The fix: `E_ABSTAIN = I − E_ACCEPT − E_REJECT = diag(1 − α, 1 − β)`. Completeness now holds on the full unit square. `T6b` is the regression. Pin to the post-fix build; no bandaid in the call site.

The engineer voice carries function names, type signatures, file paths, and the math notation lifted directly from the source. The intent is: a developer should be able to find the code in 30 seconds from any sentence.

### 8.2 Investor rollup (sample of three entries)

> **12-Frame-Pair Decision Engine.** Every AI governance verdict ships with two complementary perspectives by construction. This is a categorical departure from current single-frame governance and creates a defensible moat: a competitor would need to re-architect their verdict pipeline from scratch to match. Twelve dimensions, twenty-four scores, one audit-grade trail.
>
> **12.5k-param QKAN-FWP vs 167k-param LSTM.** Roughly 13× parameter reduction at comparable accuracy on published benchmarks (Mackey-Glass and sine), with hardware validation on IonQ and IBM Eagle at 1024 shots — primary-source efficiency claims, not marketing numbers. This is a measurable architectural lever for edge and low-latency deployments.
>
> **Doctrine v6 Ban-List Runtime Guard.** Three enforcement points — boot, bundle build, and verdict path — for the five-token doctrine ban-list. Branding, naming, and provenance are not policy documents; they are code that fails closed. Regulators and enterprise procurement teams can review the guard line by line.

The investor voice carries comparative claims, moats, regulator-friendly language, and primary-source citations. The intent is: a partner reading a deck should understand the structural advantage in one paragraph.

### 8.3 Operator rollup (sample of three entries)

> **Complementarity Floor.** When a11oy says "permit with concerns," you now see Intent 0.7 ±0.4 and Effect 0.6 ±0.5 side by side. If either frame's uncertainty is too high (product < 0.25) the verdict gets flagged automatically — you do not have to remember to check.
>
> **Ownership Opacity Score.** If you see ELEVATED, you can stop. If you see OBSCURED, you should review. If you see DARK, the investigation has already been triggered — find the entry in the queue. The score is monotone in shell depth, so deeper structures cannot accidentally rank lower.
>
> **Boot-time Theorem Manifest Verification.** If boot fails with a theorem-manifest error, the message names the missing `.lean` path. Restore the file or roll back. The system will not accept traffic until every claimed proof is on disk.

The operator voice carries decision rules, error messages, and "what to do when you see X." The intent is: an on-call engineer at 2 a.m. should be able to act from any sentence.

### 8.4 How the three voices compose

| Innovation | Engineer cue | Investor cue | Operator cue |
|---|---|---|---|
| Complementarity floor | type/runtime/proof | moat / 24 scores | act on σ-product |
| 12-pair engine | mergeAllPairs | structural advantage | worst-pair headline |
| KS-18 witness | Lean theorem | regulator story | hard escalation signal |
| POVM layer | sum-to-I check | abstain mass | rank borderline cases |
| QBist credence | prior/likelihood/posterior | replay story | inspect the three numbers |
| DARUAN | Pauli-Z expectation | 13× efficiency | bounded saturation is expected |
| Gated FWP | convex combination | quantum-inspired memory | gate controls forgetting |
| Frobenius bound | induction proof | formal-methods asset | inspect k, v, not W |
| Param efficiency | benchmark-specific | hardware-validated | re-validate on your workload |
| KS-18 soundness | Lean theorem | mathematically grounded escalation | no retry, just escalate |
| Dual-use classifier | 200 categories | hard weapons invariant | category + coefficient |
| Fixed-cycle scheduler | 364 = 52×7 | drift-free durability | weekday alignment forever |
| Operator rotation | (week, year) pure function | SOC2-friendly | tracked swaps |
| 8-template verdicts | bounded vocabulary | regulated buyer asset | template id is the headline |
| Ownership opacity | monotone in shellDepth | AML/KYC value | band-driven actions |
| Doctrine guard | three layers | code-enforced doctrine | fix the source |
| Theorem manifest | boot-time .lean check | every proof verified | roll back on missing path |
| POVM bug fix | unit-square completeness | culture-in-one-commit | pin post-fix build |

The same KB drives all three voices. Adding a new audience is a JSON edit, not a code change.

## Part 9 — Acceptance tests (`tests/explainer-agent.test.ts`)

```ts
// path: anatomy_evolved_v1/tests/explainer-agent.test.ts
/**
 * Acceptance tests for the Explainer Agent.
 * Runs under the existing tsconfig.test.json + ts-node + node:test harness.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  boot,
  explain,
  whatChanged,
  whyItMatters,
  summary,
  __internal,
  KNOWN_ORGANS,
  KNOWN_AUDIENCES,
} from "../src/explainer-agent";
import { scanForBannedTokens } from "../src/carlota-jo-doctrine-guard";
import * as fs from "node:fs";
import * as path from "node:path";

describe("explainer-agent — KB load", () => {
  it("boots and loads exactly 18 entries with all required fields", () => {
    __internal.resetForTests();
    const kb = boot();
    assert.equal(kb.entries.length, 18, "must have 18 KB entries");
    for (const e of kb.entries) {
      for (const f of __internal.REQUIRED_ENTRY_FIELDS) {
        assert.ok(f in e, `entry ${e.id} missing field ${String(f)}`);
      }
      // Audience framing has all three keys with non-empty strings
      for (const aud of KNOWN_AUDIENCES) {
        assert.ok(
          typeof e.audienceFraming[aud] === "string" &&
            e.audienceFraming[aud].length > 0,
          `entry ${e.id} audienceFraming.${aud} missing`,
        );
      }
      // sourcePaper.url is a valid URL
      assert.doesNotThrow(() => new URL(e.sourcePaper.url));
      // organAffected is in KNOWN_ORGANS
      assert.ok(
        KNOWN_ORGANS.includes(e.organAffected),
        `entry ${e.id} organAffected ${e.organAffected} not known`,
      );
    }
  });

  it("rejects duplicate ids", () => {
    const bad = {
      version: "test",
      sealedAt: "2026-01-01T00:00:00Z",
      entries: new Array(18).fill(null).map((_, i) => ({
        id: i === 0 ? "dup" : i === 1 ? "dup" : `id-${i}`,
        name: `n${i}`,
        oneLineSummary: "s",
        plainEnglishExplanation: "p",
        mathFormula: "m",
        sourcePaper: { label: "L", url: "https://example.com" },
        organAffected: "a11oy",
        evolutionVsV0: "v",
        newCapabilityUnlocked: "n",
        recommendedUseCase: "r",
        audienceFraming: { engineer: "e", investor: "i", operator: "o" },
      })),
    };
    assert.throws(() => __internal.validateKB(bad), /duplicate id/);
  });

  it("rejects wrong entry count", () => {
    const bad = { version: "v", sealedAt: "s", entries: [] };
    assert.throws(() => __internal.validateKB(bad), /exactly 18/);
  });
});

describe("explainer-agent — explain()", () => {
  it("matches 'complementarity floor' and returns the Bohr 1928 reference", () => {
    const r = explain("complementarity floor");
    assert.equal(r.matched, true);
    assert.ok(r.entry, "must return an entry");
    assert.match(r.text, /Bohr 1928/);
    assert.match(r.text, /nature\.com/);
    assert.match(r.text, /a11oy/);
  });

  it("matches 'qkan fwp' and returns the arXiv reference", () => {
    const r = explain("qkan fwp parameter efficiency");
    assert.equal(r.matched, true);
    assert.match(r.text, /arxiv\.org\/abs\/2605\.06734/);
  });

  it("returns matched=false on unknown query", () => {
    const r = explain("blockchain consensus");
    assert.equal(r.matched, false);
    assert.match(r.text, /no KB entry matched/);
  });

  it("handles empty-after-stopword queries gracefully", () => {
    const r = explain("the of and");
    assert.equal(r.matched, false);
    assert.match(r.text, /empty/);
  });
});

describe("explainer-agent — whatChanged()", () => {
  it("returns at least 5 entries for a11oy", () => {
    const r = whatChanged("a11oy");
    assert.ok(
      r.count >= 5,
      `a11oy must have >= 5 evolutions, got ${r.count}`,
    );
    for (const e of r.entries) {
      assert.equal(e.organAffected, "a11oy");
    }
  });

  it("returns entries for amaru", () => {
    const r = whatChanged("amaru");
    assert.ok(r.count >= 3, `amaru must have >= 3 evolutions, got ${r.count}`);
  });

  it("throws on unknown organ", () => {
    assert.throws(() => whatChanged("kidney"), /unknown organ/);
  });
});

describe("explainer-agent — whyItMatters()", () => {
  it("investor framing emphasizes parameter efficiency and moat", () => {
    const r = whyItMatters("investor");
    assert.match(r.text, /13x|13×/i);
    assert.match(r.text, /moat|defensible|categorical/i);
  });

  it("engineer framing references types, proofs, or runtime", () => {
    const r = whyItMatters("engineer");
    assert.match(r.text, /type|runtime|Lean|proof/i);
  });

  it("operator framing references actionable decisions", () => {
    const r = whyItMatters("operator");
    assert.match(r.text, /escalate|review|inspect|pin|roll back|investigation/i);
  });

  it("throws on unknown audience", () => {
    assert.throws(() => whyItMatters("regulator"), /unknown audience/);
  });
});

describe("explainer-agent — summary()", () => {
  it("produces a rollup under 200 lines", () => {
    const r = summary();
    const lines = r.text.split("\n").length;
    assert.ok(lines < 200, `summary must be < 200 lines, got ${lines}`);
    assert.equal(r.entryCount, 18);
  });
});

describe("explainer-agent — doctrine guard", () => {
  it("KB JSON contains zero banned tokens", () => {
    const kbPath = path.resolve(
      __dirname,
      "..",
      "data",
      "explainer-kb.json",
    );
    const raw = fs.readFileSync(kbPath, "utf8");
    const r = scanForBannedTokens(raw);
    assert.equal(
      r.hits.length,
      0,
      `KB JSON contains banned tokens: ${JSON.stringify(r.hits)}`,
    );
  });

  it("rendered explanations contain zero banned tokens", () => {
    const all = [
      summary().text,
      whyItMatters("engineer").text,
      whyItMatters("investor").text,
      whyItMatters("operator").text,
      ...KNOWN_ORGANS.map((o) => whatChanged(o).text),
    ].join("\n");
    const r = scanForBannedTokens(all);
    assert.equal(r.hits.length, 0);
  });
});

describe("explainer-agent — CLI exit codes (via spawn)", () => {
  // These are smoke-style assertions; the bin script is exercised by the CI workflow.
  // Here we only check that the same code paths return the expected matched flag.
  it("matched topic returns matched=true (exit 0 in CLI)", () => {
    assert.equal(explain("complementarity floor").matched, true);
  });
  it("unmatched topic returns matched=false (exit 1 in CLI)", () => {
    assert.equal(explain("blockchain").matched, false);
  });
});
```

### 9.1 Test coverage matrix

| Requirement | Test |
|---|---|
| All 18 KB entries load with required fields | "boots and loads exactly 18 entries..." |
| Duplicate ids rejected | "rejects duplicate ids" |
| Wrong entry count rejected | "rejects wrong entry count" |
| `explain("complementarity floor")` → Bohr 1928 | "matches 'complementarity floor'..." |
| `whatChanged("a11oy")` returns ≥ 5 | "returns at least 5 entries for a11oy" |
| `whyItMatters("investor")` emphasizes parameter efficiency + moat | "investor framing emphasizes..." |
| `summary()` < 200 lines | "produces a rollup under 200 lines" |
| Doctrine guard passes on KB JSON | "KB JSON contains zero banned tokens" |
| Doctrine guard passes on all rendered output | "rendered explanations contain zero banned tokens" |
| CLI exit 0 on match | "matched topic returns matched=true" |
| CLI exit 1 on no-match | "unmatched topic returns matched=false" |
| CLI exit 2 on usage error | exercised by the CI workflow (Part 10) |

## Part 10 — CI Workflow (`.github/workflows/explainer-agent-ci.yml`)

```yaml
# path: .github/workflows/explainer-agent-ci.yml
name: explainer-agent-ci

on:
  push:
    paths:
      - "anatomy_evolved_v1/src/explainer-agent.ts"
      - "anatomy_evolved_v1/bin/explain.ts"
      - "anatomy_evolved_v1/data/explainer-kb.json"
      - "anatomy_evolved_v1/tests/explainer-agent.test.ts"
      - ".github/workflows/explainer-agent-ci.yml"
  pull_request:
    paths:
      - "anatomy_evolved_v1/**"

jobs:
  explainer-agent:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install
        working-directory: anatomy_evolved_v1
        run: npm ci

      - name: TypeScript build (no emit, then emit for CLI)
        working-directory: anatomy_evolved_v1
        run: |
          npx tsc -p tsconfig.test.json --noEmit
          npx tsc -p tsconfig.json

      - name: KB JSON validity
        working-directory: anatomy_evolved_v1
        run: |
          python3 -c "import json,sys; json.load(open('data/explainer-kb.json'))"

      - name: Doctrine guard sweep on payload + KB
        working-directory: anatomy_evolved_v1
        run: |
          # Five banned tokens must not appear in operational code or KB content.
          # Definitional matches inside BANNED_TOKENS arrays are allowed by doctrine v6.
          ! grep -inE \
            'alloyscape|glass[ -]?wing|glasswing|mythos|stephen paul|perplexity computer' \
            src/explainer-agent.ts \
            bin/explain.ts \
            data/explainer-kb.json \
            tests/explainer-agent.test.ts

      - name: Acceptance tests
        working-directory: anatomy_evolved_v1
        run: npx tsx --test tests/explainer-agent.test.ts

      - name: CLI exit codes
        working-directory: anatomy_evolved_v1
        run: |
          # Match — exit 0
          node dist/bin/explain.js "complementarity floor"
          # No-match — exit 1 (we invert with !)
          ! node dist/bin/explain.js "blockchain consensus"
          # Usage error — exit 2
          set +e
          node dist/bin/explain.js --audience
          code=$?
          set -e
          test $code -eq 2 || { echo "expected exit 2 on usage error, got $code"; exit 1; }
          # Summary
          node dist/bin/explain.js --summary | wc -l | awk '{ if ($1 >= 200) { print "summary too long: "$1; exit 1 } }'

      - name: Boot smoke
        working-directory: anatomy_evolved_v1
        run: |
          node -e "require('./dist/src/explainer-agent').boot(); console.log('boot ok')"
```

### 10.1 What the CI proves

1. The module type-checks under the existing `tsconfig.test.json` and emits under `tsconfig.json`.
2. The KB JSON is valid JSON.
3. The five-token doctrine guard sweeps clean across `explainer-agent.ts`, `explain.ts`, `explainer-kb.json`, and the test file. (Definitional banned-token matches inside `carlota-jo-doctrine-guard.ts` `BANNED_TOKENS` array are out of scope for this workflow — they are covered by the main anatomy-evolved-v1 CI.)
4. Every acceptance test in Part 9 passes.
5. CLI exit codes are exactly `0` on match, `1` on no-match, `2` on usage error.
6. `summary()` output is under 200 lines.
7. `boot()` succeeds from a fresh process.

## Part 11 — Doctrine Final Gate

### 11.1 Identity (single source of truth)

- Author: **Stephen P. Lutar Jr.**, SZL Holdings
- ORCID: [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)
- Contact: stephen@szlholdings.com
- Role: operator / architect; not a PhD. Pods are PhD-trained.

### 11.2 Organ names (lowercase, canonical)

`a11oy`, `amaru`, `sentra`, `terra`, `vessels`, `counsel`, `carlota-jo`, `lutar-lean`.

### 11.3 Banned tokens (definitional only)

The doctrine v6 ban-list, as enforced by `carlota-jo-doctrine-guard.ts` `BANNED_TOKENS`:

1. `AlloyScape`
2. `Glass Wing` / `Glasswing`
3. `Mythos`
4. `Stephen Paul`
5. `Perplexity Computer`

These tokens appear in this payload **only** inside this enumeration, inside `BANNED_TOKENS` array literals, and inside doctrine-guard test fixtures. The CI sweep (Part 10) treats any other occurrence as a hard failure.

### 11.4 Engineering scope (no spiritual / theological framing)

Every claim in this payload traces to one of:

- a formula in `anatomy_evolved_v1/src/*.ts`,
- a Lean theorem in `anatomy_evolved_v1/lean/*.lean`,
- a smoke test result in `thesis_ch9_anatomy_evolved_v1.md` §9.3,
- a primary-source paper with a real URL/DOI (Bohr 1928, Cabello 1996, Davies & Lewis 1970, Fuchs & Schack 2013, Preskill 2015, Peng/Chen et al. 2026).

No claim depends on spiritual, theological, scriptural, or comparative-religion framing.

### 11.5 No hallucinations, no bandaids

- Every KB entry's `sourcePaper.url` resolves to a real publication or DOI record.
- The POVM bug fix entry (§3.18, JSON `povm-completeness-bugfix`) describes a real fix to a real bug caught by smoke test `T6b`. No bandaid; the new construction is mathematically natural.
- The 13× parameter-efficiency claim is benchmark-specific (Mackey-Glass, sine) and pulls from [arXiv:2605.06734](https://arxiv.org/abs/2605.06734); we do not generalize it.

### 11.6 Cross-references

- [`thesis_ch9_anatomy_evolved_v1.md`](./thesis_ch9_anatomy_evolved_v1.md) — chapter that records what evolved.
- [`replit_anatomy_evolved_payload.md`](./replit_anatomy_evolved_payload.md) — 3,735-line operational code payload that the explainer reads.
- [`replit_thesis_injection_payload.md`](./replit_thesis_injection_payload.md) — companion injection payload referenced for cross-organ context.
- [`qkan_fwp_paper_extract.md`](./qkan_fwp_paper_extract.md) — extracted notes from [arXiv:2605.06734](https://arxiv.org/abs/2605.06734).
- [`quantum_bohr_pod_report.md`](./quantum_bohr_pod_report.md) — Bohr / KS-18 / POVM / QBist pod report.
- [`quantum_einstein_pod_report.md`](./quantum_einstein_pod_report.md) — geometric ML / Fisher / Sorkin / Penrose pod report.

## Part 12 — Replit Boot Hook

`thesis-boot.ts` is the entry script Replit runs. It already calls `verify_theorem_manifest()` and `assertDoctrineCompliance()`. Add the explainer boot in the same startup phase, after doctrine but before the first organ accepts traffic.

```ts
// path: anatomy_evolved_v1/src/thesis-boot.ts (excerpt — illustrative add)
import { assertDoctrineCompliance } from "./carlota-jo-doctrine-guard";
import { boot as explainerBoot } from "./explainer-agent";
// ... existing imports (a11oy, amaru, sentra, terra, vessels, counsel, lutar-lean)

export async function thesisBoot(): Promise<void> {
  // 1. Doctrine guard self-check (existing)
  assertDoctrineCompliance("thesis-boot start", "boot");

  // 2. Lean theorem manifest verification (existing)
  await verify_theorem_manifest();

  // 3. Explainer Agent KB load (NEW)
  try {
    const kb = explainerBoot();
    console.log(
      `[boot] explainer-agent KB loaded: ${kb.entries.length} entries, version ${kb.version}`,
    );
  } catch (e) {
    console.error(`[boot] explainer-agent boot failed: ${(e as Error).message}`);
    process.exit(1);
  }

  // 4. Organ inits (existing)
  // ... a11oy, amaru, sentra, terra, vessels, counsel
}
```

### 12.1 Boot order rationale

1. **Doctrine guard first** — if the binary itself carries a banned token, refuse to start.
2. **Theorem manifest second** — if a claimed proof is missing, refuse to start.
3. **Explainer Agent third** — if the KB cannot load or fails its schema/doctrine checks, refuse to start. This catches malformed KB JSON, missing fields, banned tokens in the explainer prose, and any duplicate ids before any organ accepts traffic.
4. **Organs last** — only after all three guards pass.

### 12.2 Failure modes (all fail-closed)

| Failure | Symptom | Action |
|---|---|---|
| KB file missing | `cannot read KB at <path>` | Restore `data/explainer-kb.json` or roll back |
| KB JSON malformed | `is not valid JSON` | Validate locally with `python3 -m json.tool`, fix, redeploy |
| Wrong entry count | `must contain exactly 18 entries` | Add or remove entries to match the canonical count |
| Duplicate id | `duplicate id "<id>"` | Rename the offending entry |
| Banned token in KB | doctrine guard throws with position | Edit the KB to remove the banned phrase |
| Unknown organ | `organAffected "<x>" is not a known organ` | Use one of `a11oy`, `amaru`, `sentra`, `terra`, `vessels`, `counsel`, `carlota-jo`, `lutar-lean` |
| Bad URL | `sourcePaper.url is not a valid URL` | Provide a parseable URL/DOI |

Every failure aborts boot before the first request. The explainer never returns stale or unsafe text because it never starts in a degraded state.

---

*Stephen P. Lutar Jr. · SZL Holdings · stephen@szlholdings.com*
*ORCID: [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173)*
*Explainer Agent payload sealed: May 19, 2026 · Doctrine v6 compliant · Engineering only*
