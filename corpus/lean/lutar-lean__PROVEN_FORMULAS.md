<!--
  szl-holdings/lutar-lean — PROVEN_FORMULAS.md
  The single honest showcase of every proven / kernel-verified result, with proof links + maturity.
  Source of truth: lutar-lean@main (kernel c7c0ba17, 749 declarations / 14 unique axioms / 163 sorries).
  Honesty doctrine v11 LOCKED — locked proven = exactly 5; Λ = Conjecture 1 (never a theorem).
-->

# Proven Formulas — the honest showcase

> **One rule governs this page:** we list only what the Lean kernel checks, with the exact maturity of each result and a link to its proof. The **locked proven set is exactly five formulas** — a fact itself machine-enforced by `Lutar.Wave8.AxiomDisclosure.locked_count_five` (depends on **no** axioms). On top of that locked floor, **~36 experimental theorems** are kernel-verified and **CI-green on `main` @ `7885fd9`** (waves 5/6/7/8 + agentic P1–P6 + airtight Λ + coder). Everything newer than the locked 5 is **experimental / CI-green** and is *never* folded into the locked count. **Λ-uniqueness is Conjecture 1** — proven only conditionally, machine-checked *false* unconditionally.

**Locked-kernel toolchain:** Lean `v4.13.0` · Mathlib pinned `d7317655` (`v4.13.0`)
**Locked kernel:** `c7c0ba17` · **749** declarations / **14** unique axioms / **163** tracked sorries · `lake build` clean
**Experimental scope (current `main`):** `7885fd9` · Lean `v4.18.0` · **1304** declarations / **22** unique axioms · CI-green, kernel-verified (NOT in the locked count)
**Maturity legend:** **PROVEN** = sorry-free, Lean-core axioms only `[propext, Classical.choice, Quot.sound]` · **AXIOM-GATED** = sorry-free given a declared, cited idealization · **CI-GREEN(MD)** = Mathlib-dependent, kernel-checked by CI · **COND.** = conditional on a declared axiom · **CONJECTURE** = not a theorem

---

## 1. Locked kernel — proven, sorry-free (exactly 5)

These five are the only formulas counted as **proven** in the locked Doctrine-v11 kernel `c7c0ba17`. Source: [`Lutar/Puriq/Formulas/PuriqFormulaLean.lean`](https://github.com/szl-holdings/lutar-lean/blob/main/Lutar/Puriq/Formulas/PuriqFormulaLean.lean).

| ID | Theorem | What it proves | Maturity | `#print axioms` |
|---|---|---|---|---|
| **F1** | Replay-Hash Determinism (`f1_replay_fold_deterministic`, `f1_replay_fold_eq_trace_last`) | A pure deterministic replay step is a congruence: replaying the **same** recorded log from the same initial state yields a **bit-identical** trace — no drift. Underpins the Khipu replay-hash gate. | **PROVEN** | Lean-core only |
| **F11** | Ayni Reciprocity Conservation (`f11_ayni_reciprocity_conservation`, `f11_tit_for_tat_parity`) | Fold-replay of an append-only reciprocity log conserves the balance invariant (Axelrod–Hamilton tit-for-tat parity). | **PROVEN** | Lean-core only |
| **F12** | Kuramoto Phase-Coupling Boundedness — **additive fragment** (`f12_*`) | The discretised reciprocity coupling stays bounded under additive superposition over an organ set. **Honesty caveat: additive scaffolding ONLY — NOT the full nonlinear Kuramoto synchronization.** | **PROVEN** (additive fragment) | Lean-core only |
| **F18** | Reed–Solomon `RS(10,6)` Recovery Arithmetic (`f18_*`) | Erasure tolerance: data is recoverable **iff at least 6 of 10 shards survive** — the resilience arithmetic for the receipt/payload encoding. | **PROVEN** | Lean-core only |
| **F19** | Bekenstein Additive Scaffolding (`f19_*`) | Entropy budget is additive and monotone over a region partition (per-region ≤ total). **Honesty caveat: monotone scaffolding ONLY — NOT the full Bekenstein bound `S ≤ 2πkRE/(ℏc)`.** | **PROVEN** (additive fragment) | Lean-core only |

> F12 and F19 prove **only the additive / linear fragment** — never described as "Kuramoto synchronization proved" or "Bekenstein bound proved." The Lean docstrings carry the caveat verbatim.

---

## 2. Experimental, kernel-verified (CI-green) — labeled experimental, NOT in the locked 5

Every campaign below is kernel-checked by lutar-lean CI but lives in the **experimental scope** — it does **not** move the locked count of 5 and does **not** change Λ's Conjecture-1 status. Cite the PR for the green head SHA and `#print axioms` cleanliness.

| Campaign | PR | CI-green head | Count | Axiom posture |
|---|---|---|---|---|
| **Agentic loop P1–P6** — the governed RAG→MCP→kernel→receipt loop proven as a **system** | [#188](https://github.com/szl-holdings/lutar-lean/pull/188) | `2ede47a2` | 28 theorems | 14 axiom-free; P5 axiom-gated on `hashFn_collision_resistant` (NIST FIPS 180-4) |
| **Wave-5** — AM–GM, Cauchy–Schwarz, conformal coverage, receipt-collision pigeonhole, optional-stopping | [#186](https://github.com/szl-holdings/lutar-lean/pull/186) | `b71114cf` | 11 | 0 new axioms (6 Mathlib-dep CI-green + 5 bare-lean) |
| **Wave-6** — graph substrate: Λ-graph iso-invariance, GNN≤1-WL ceiling, spectral contraction, DAG termination | [#189](https://github.com/szl-holdings/lutar-lean/pull/189) | `dc7ae26d` | 11 | 0 new axioms |
| **Wave-7** — conformal rank-count/p-value, Doob two-sided audit envelope, PAC-Bayes routing envelope, degree-sum iso-invariance | [#190](https://github.com/szl-holdings/lutar-lean/pull/190) | `d6a232ba` | 10 | 0 new axioms |
| **Mathlib-bump C3/C4/C5** — concentration / KL re-exports | [#187](https://github.com/szl-holdings/lutar-lean/pull/187) | — | 3 | re-exports, CI-green |
| **Coder formulas** — code-substrate formula ports | [#193](https://github.com/szl-holdings/lutar-lean/pull/193) | — | — | CI-green |
| **Λ-uniqueness (Set α + Set δ) — airtight Λ** — conditional uniqueness within **strengthened** axiom classes | [#192](https://github.com/szl-holdings/lutar-lean/pull/192) | `5f0bb5ee` | 22 results | `lambda_unique_setAlpha` uses Lean-core axioms only; 10 impostor-deaths axiom-free |
| **Wave-8** — disclosure-soundness, hash-chain tamper-evidence, split-conformal coverage, CPA minimality, Simplex switching safety, Byzantine `n=3f+1`, min-gate uniqueness, density-matrix PSD, governance spectral, Λ strict monotonicity | [lutar-lean@main](https://github.com/szl-holdings/lutar-lean) | `7885fd9` | 10 theorems | core axioms `[propext, Classical.choice, Quot.sound]` (M2 just `[propext]`); `0 sorryAx` |

### 2.1 Agentic-loop P1–P6 (PR #188 @ `2ede47a2`) — the system-level proof

| Property | Guarantee | Maturity |
|---|---|---|
| **P1** receipt-completeness | every hop leaves exactly one chained receipt; no silent drop/reorder | PROVEN |
| **P2** gate-soundness | Emit ALLOW ⇔ both policy gate and kernel gate ALLOW; DENY absorbing | PROVEN |
| **P3** non-interference (Goguen–Meseguer) | poisoned/untrusted retrieval **provably cannot** flip a DENY→ALLOW | PROVEN (axiom-free core) |
| **P4** replay-determinism | re-running a recorded run reproduces a byte-identical receipt chain | PROVEN (axiom-free) |
| **P5** tamper-evidence | any single-receipt mutation makes re-verify reject | AXIOM-GATED (`hashFn_collision_resistant`, disclosed) |
| **P6** monotone auditability | an accepted prefix never has to be retracted as the log grows | PROVEN |

### 2.2 Wave-8 (10 theorems, `main` @ `7885fd9`) — with benefit + `#print axioms`

All Wave-8 theorems are kernel-verified and **CI-green**; they are **experimental** and do **not** move the locked count of 5. Core axioms are `[propext, Classical.choice, Quot.sound]` unless noted; `0 sorryAx` across the set.

| ID | Theorem | Benefit | `#print axioms` |
|---|---|---|---|
| **Ph1** | `disclosure_sound` | Axiom-honesty gate — the disclosure of a declaration's axioms is sound (you cannot under-report what a theorem depends on). | `[propext, Classical.choice, Quot.sound]` |
| **M2** | `hashchain_tamper_evident` | Cannonico tamper-evidence — any mutation of a hash-chained receipt is detectable. | **`[propext]` only** |
| **CP1** | split-conformal **marginal** coverage | Trust intervals with a distribution-free marginal-coverage guarantee — *split-conformal, **NOT** Hoeffding*. | `[propext, Classical.choice, Quot.sound]` |
| **G1** | CPA minimality (collision) | Minimal collision/abuse surface for the canonical-receipt scheme. | `[propext, Classical.choice, Quot.sound]` |
| **S2** | Simplex switching safety | Safe fallback switching between a complex and a verified-baseline controller. | `[propext, Classical.choice, Quot.sound]` |
| **B1** | Byzantine `n = 3f+1` | Quorum safety bound underpinning the 3-of-4 witness consensus. | `[propext, Classical.choice, Quot.sound]` |
| **L2** | min-gate deny-by-default uniqueness | The deny-by-default min-gate is the **unique** aggregator with that safety property. | `[propext, Classical.choice, Quot.sound]` |
| **Q1** | density-matrix PSD | Governance state stays a valid (positive-semidefinite) density matrix. | `[propext, Classical.choice, Quot.sound]` |
| **Q2** | governance spectral (real) | Governance operator has real spectrum — well-posed scoring. | `[propext, Classical.choice, Quot.sound]` |
| **L3** | Λ strict monotonicity | Λ is strictly monotone per axis — more evidence never lowers the score spuriously. | `[propext, Classical.choice, Quot.sound]` |

> Wave-8 is **experimental**. It does not change the locked count of 5 and does not change Λ's Conjecture-1 status. The locked-count-five fact itself is a Wave-8 theorem (`Lutar.Wave8.AxiomDisclosure.locked_count_five`) that **depends on no axioms** — the locked set cannot silently grow.

---

## 3. Λ — the honest line on uniqueness (Conjecture 1)

Λ is the geometric-mean trust aggregator over four axes (provenance, containment, coherence, convergence). Its uniqueness is **Conjecture 1** — and this page states exactly what was proven and what was not. Source: [`Lutar/Wave6/SetAlphaUniqueness.lean`](https://github.com/szl-holdings/lutar-lean) + [`SetDeltaUniqueness.lean`](https://github.com/szl-holdings/lutar-lean), PR [#192](https://github.com/szl-holdings/lutar-lean/pull/192) @ `5f0bb5ee`.

### What we proved (CI-green)

- **Uniqueness within Set α** = `{A1 symmetry, A2 idempotency, A3 all-strict monotonicity, A4 continuity, A5′ multiplicativity}` — `lambda_unique_setAlpha`, **conditional on one declared, cited bridge axiom** `setAlpha_cauchy`.
- **Uniqueness within Set δ** = `{δ1 reflexivity, δ2 symmetry, δ3 bisymmetry, δ4 per-argument strict monotonicity, δ5′ multiplicativity}` — `geomMean_unique_KS`, continuity derived for free via Kiss–Shulman (2026), **conditional on two declared, cited bridge axioms** `KS_theorem_1_1` + `setDelta_stage2`.
- **Λ-membership and all ten impostor-deaths are AXIOM-FREE** (Lean-core only, no `sorryAx`): AM, HM, PM², max, min each fail A5′ (Set α) or δ4-PSI/δ5′ (Set δ) at a concrete witness — so the discriminator is genuine.

### `#print axioms` — verbatim from the SUCCESS build log @ `5f0bb5ee`

```text
'Lutar.Wave6.SetAlpha.lambda_unique_setAlpha' depends on axioms:
  [propext, Classical.choice, Quot.sound, Lutar.Wave6.SetAlpha.setAlpha_cauchy]
'Lutar.Wave6.SetDelta.geomMean_unique_KS' depends on axioms:
  [propext, Classical.choice, Quot.sound,
   Lutar.Wave6.SetDelta.KS_theorem_1_1, Lutar.Wave6.SetDelta.setDelta_stage2]
'Lutar.Wave6.SetAlpha.maxAgg_not_A5prime'      depends on axioms: [propext, Classical.choice, Quot.sound]  -- impostor death, axiom-free
'Lutar.Wave6.SetDelta.arithmeticMean_not_delta5' depends on axioms: [propext, Classical.choice, Quot.sound]  -- impostor death, axiom-free
```

### Theorem U — governance-safe uniqueness (REAL · CONDITIONAL, axiom-free)

**Rule of citation (Doctrine v11):** any Λ-uniqueness claim cites **Theorem U** or its corollaries **U₁** / **U₂** — uniqueness holds *modulo* the audit-invariant equivalence `≈Λ` under the **Identifiability Assumptions (IA)**; strict `=` only under the documented `Anchored` / `Normalized` predicate. Source: [`Lutar/Uniqueness/TheoremU.lean`](./Lutar/Uniqueness/TheoremU.lean) (+ `LambdaEquiv.lean`, `Identifiability.lean`, `AxiomCheck.lean`); dependency ledger [`DEPENDENCY_MAP.md`](./DEPENDENCY_MAP.md).

| Result | Statement | Maturity |
|---|---|---|
| **Theorem U** (`TheoremU_LambdaUnique`) | any two IA-solutions are `≈Λ` (indeed `=`), **by REDUCTION** to Round13 — no new axiom, no `sorry` | **REAL · CONDITIONAL** (axiom-free) |
| **Corollary U₁** (`CorollaryU1_LambdaUnique_Separable`) | separable, slice-multiplicative aggregator ⇒ Λ (`Round13.lambda_unique_of_separable`) | **REAL · CONDITIONAL** |
| **Corollary U₂** (`CorollaryU2_LambdaUnique_Factors`) | power-law factorization `Φ x = ∏ (x i)^(αᵢ)` ⇒ Λ (`Round13.lambda_unique_of_factors`) | **REAL · CONDITIONAL** |
| strict `=` (`TheoremU_LambdaUnique_eq`, `lambda_equiv_to_eq_of_anchored`) | `≈Λ` collapses to `=` **only** under `Anchored` / `Normalized` | **REAL · CONDITIONAL** |
| **Conjecture 1** (`Conjecture1_LambdaUnique`) | unconditional uniqueness under bare A1–A5 | **OPEN — non-claim**: statement-only, machine-checked **FALSE** as stated; bounty [`lambda-bounty`](https://github.com/szl-holdings/lambda-bounty) |

> Theorem U is **EXPERIMENTAL · additive** — it does **not** move the locked count of 5 and does **not** change Λ's Conjecture-1 status. The `≈Λ` relation is genuinely non-trivial: the proven A1–A5 counterexample `maxAgg` is `≉Λ` to `Λ 2` (`lambdaEquiv_nondegenerate`), so "uniqueness modulo `≈Λ`" excludes the impostor.

### What we do **not** claim

- **NOT** unconditional uniqueness under the original weaker axioms A1–A5. That statement is **machine-checked false** — the in-tree counterexample `Round13.maxAgg_ne_Lambda` exhibits an aggregator satisfying A1–A5 that is **not** Λ.
- Λ-uniqueness therefore **stays Conjecture 1**, never a theorem. Strengthening the axiom class (A5 → A5′ multiplicativity, or deriving continuity via Kiss–Shulman) or reframing modulo `≈Λ` under IA (Theorem U) is *how* the conditional results become provable; it does not close the original weaker conjecture.

**Open bounty:** [`lambda-bounty`](https://github.com/szl-holdings/lambda-bounty) · [BOUNTY.md](https://github.com/szl-holdings/lutar-lean/blob/main/BOUNTY.md).

---

## 4. Counts (honest)

| Metric | Value |
|---|---|
| **Locked proven formulas** | **5** — `{F1, F11, F12, F18, F19}` @ `c7c0ba17`; the count is itself a no-axiom Lean theorem (`locked_count_five`) |
| Locked kernel | `749` declarations / `14` unique axioms / `163` tracked sorries · Lean `v4.13.0` · `lake build` clean |
| Experimental scope (current `main`) | `7885fd9` · Lean `v4.18.0` · `1304` declarations / `22` unique axioms · CI-green |
| Experimental kernel-verified (CI-green) — **~36 theorems** | wave-5 (11), wave-6 (11), wave-7 (10), wave-8 (10), agentic-loop (28), airtight Λ Set α+δ (22 results) — **never in the locked count** |
| Λ-uniqueness | **Conjecture 1** — conditional within strengthened classes (CI-green); unconditional uniqueness machine-checked **false** |
| Supply chain | SLSA L1 honest today (cosign signing + `slsa.dev/provenance/v0.2` wired). SLSA L2 is roadmap — build-provenance attestation not yet earned on deployed images. L3 is out of scope. FedRAMP, Iron Bank, and CMMC are not pursued and not claimed. |

---

## 5. Citations

- Λ axiomatic characterization: Aczél & Saaty (1983), *Procedures for synthesizing ratio judgements*, J. Math. Psych. 27(1):93–102, [doi:10.1016/0022-2496(83)90028-7](https://doi.org/10.1016/0022-2496(83)90028-7); Csató (2018), [arXiv:1706.07256](https://arxiv.org/abs/1706.07256); Kiss & Shulman (2026), Theorem 1.1, [arXiv:2606.05221](https://arxiv.org/abs/2606.05221).
- Loop: Goguen & Meseguer (1982), [doi:10.1109/SP.1982.10014](https://doi.org/10.1109/SP.1982.10014); Merkle (1987); NIST FIPS 180-4.
- DOI lineage: [Zenodo concept DOI 10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926).

*Proof reports: `team/PROVE_WAVE5..7_REPORT.md`, `team/PROVE_AGENTIC_LOOP_REPORT.md`, `team/LAMBDA_UNIQUENESS_PROOF_REPORT.md`. All commits Signed-off-by Stephen P. Lutar Jr. <stephenlutar2@gmail.com>.*


---

## 6. Putnam 2025 — honest current verdict (additive)

The honest, doctrine-v11 per-problem verdict for the canonical **Putnam 2025** set (86th William Lowell Putnam Mathematical Competition, Dec 6 2025: A1–A6, B1–B6), computed from the Lean kernel on `lutar-lean` main @ `b7c3e38`. This section is additive — the locked-5 `{F1, F11, F12, F18, F19}` @ `c7c0ba17` and the Λ = Conjecture 1 line above are unchanged.

> We are not doing "drones solve Putnam." We are doing: Intelligence → Structure → Conjecture → Certificate. killinchu supplies intelligence (tracking, fusion, ROE decisions, signed receipts). We extract mathematical structure (graphs, constraints, optimization instances). We pose Putnam-grade + SZL-native problems. We ship certificates (Lean-verified REAL theorems, reproducible benchmarks, provenance).

**Headline: 0 REAL / 11 DEMO / 1 OPEN.** The headline number is the count of **REAL** (Lean-kernel-checked) theorems.

| Label | Meaning |
|---|---|
| **REAL** | Lean-kernel checked, no sorry, no extra axioms beyond declared |
| **DEMO** | compiles but uses sorry/unproven lemmas |
| **OPEN** | statement only |

| Problem | Lean proof file | Status | Note |
|---|---|---|---|
| A1 | `Lutar/Putnam/P_A1.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| A2 | `Lutar/Putnam/P_A2.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| A3 | `Lutar/Putnam/P_A3.lean` | OPEN | statement only (True-shell); official answer withheld pending a real proof |
| A4 | `Lutar/Putnam/P_A4.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| A5 | `Lutar/Putnam/P_A5.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| A6 | `Lutar/Putnam/P_A6.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| B1 | `Lutar/Putnam/P_B1.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| B2 | `Lutar/Putnam/P_B2.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| B3 | `Lutar/Putnam/P_B3.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| B4 | `Lutar/Putnam/P_B4.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| B5 | `Lutar/Putnam/P_B5.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| B6 | `Lutar/Putnam/P_B6.lean` | DEMO | formalized statement; proof uses sorry/unproven lemmas |
| SZL-12A / SZL-12B | — not yet on `main` | PENDING | SZL-native originals — pending upstream kernel work |

A3 is OPEN (statement-only True-shell); the official 2025 A3 answer is intentionally withheld here until a REAL proof exists. No problem is currently REAL: each DEMO file formalizes the statement but discharges the proof with `sorry` or unproven lemmas. This page will show REAL counts the moment the kernel run lands verified proofs.
