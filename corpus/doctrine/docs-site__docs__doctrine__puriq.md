# PURIQ Doctrine (v12) — the agentic-action layer

<div class="quechua">
<strong>PURIQ</strong> — from Quechua <strong><em>puriy</em></strong>, the intransitive verb
"to walk / to go", whose agentive (nominaliser <code>-q</code>) form
<strong><em>puriq</em></strong> means "<strong>the one who walks / the walker / the one who
acts</strong>". The morphology is the whole point: <code>-q</code> turns a process verb into
the <em>agent</em> that performs it. Sources:
<a href="https://en.wiktionary.org/wiki/puriy">Wiktionary <em>puriy</em></a> (conjugation
table, infinitive <code>puriy</code> → agentive <code>puriq</code>),
<a href="https://qu.wiktionary.org/wiki/puriq">Quechua Wiktionary <em>puriq</em></a> ("walker /
caminante / piéton"), and the peer-reviewed ethnomusicology of the Cusco region
(<a href="https://www.erudit.org/en/journals/fr/2018-v29-n2-fr03541/1044160ar.pdf">La Riva
González, <em>Puriq wayra</em>, érudit, 2018</a>). <strong>No mystical terms</strong> appear in
this layer — every name is a cited Quechua common noun or a math primitive already in v11.
</div>

PURIQ is the layer that turns the anatomy from *a thing that evaluates* into *an agent that
acts*. Doctrine v12 = **Doctrine v11 + PURIQ**: it carries forward every v11
[LOCKED number](/doctrine/v11-v12) verbatim and adds one thing — a single, Lean-stateable
**action-selection operator** so that *agency itself*, not just admission, is governed.

> **Full text:** the canonical Doctrine v12 document is `doctrine/PURIQ_DOCTRINE_v12.md`; the
> per-organ specialisations are in `doctrine/sub_formulas/PURIQ_SUBFORMULAS_v12.md`; the proof
> obligations are in `formulas/PuriqLean.lean` (all `sorry`-tagged). These live in the SZL
> PURIQ workspace and feed [`lutar-lean`](https://github.com/szl-holdings/lutar-lean).

## The definition of "agentic" (locked)

An action is **agentic** iff it is selected by `P(x,t)` under all four invariants below —
i.e. it is **Λ-bounded**, **Yuyay-gated**, **HUKLLA-safe**, and **Khipu-receipted**. An LLM
call that lacks any one of the four is **not** agentic under this doctrine; it is an
ungoverned emission.

## The master formula `P(x,t)`

For an evaluation context `x` at decision step `t`, over a bounded action space $\mathcal{A}$,
the selected action is

$$ P(x,t) = \operatorname*{arg\,max}_{a \in \mathcal{A}} \Big[\; \Lambda(x)\cdot \mathrm{Yuyay}_{13}(a)\cdot \exp\!\big(-\beta\cdot\mathrm{HUKLLA}(a)\big)\cdot \textstyle\prod_i \mathrm{Khipu}_i(a)\;\Big]. $$

We call the bracketed scalar the **Puriq utility** of action `a`:

$$ U(a\mid x) := \Lambda(x)\cdot\mathrm{Yuyay}_{13}(a)\cdot e^{-\beta\,\mathrm{HUKLLA}(a)}\cdot\prod_{i=1}^{m}\mathrm{Khipu}_i(a),\qquad P(x,t)=\operatorname*{arg\,max}_{a\in\mathcal{A}} U(a\mid x). $$

### Term definitions

| Term | Type | Definition | v11 anchor |
|------|------|------------|------------|
| $\Lambda(x)$ | $\mathbb{R}_{\ge 0}$ | Lambda-Spine aggregator: the weighted geometric mean $\prod x_i^{w_i}$, $\sum w_i=1$ (definition **D2**). Positive-homogeneous (**A2 = `IsHomogeneous`**), monotone (A1), bounded (**A4 = `IsBounded`**). | v11 §12; `Lutar/Axioms.lean` |
| $\mathrm{Yuyay}_{13}(a)$ | $[0,1]$ | 13-axis `yuyay_v3` score. Conjunctive AND: 0 unless all 13 axes clear floors (2 sacred ≥ 0.95, 7 structural ≥ 0.90, 4 introspection ↔ HUKLLA T03/T04/T09/T10). Replay-hash `bacf5443…631fc5`. | v11 §1–§2 |
| $\mathrm{HUKLLA}(a)$ | $\mathbb{N}$ | Count of fired tripwires among T01–T10. 0 ⇔ clean. T10 (STOP/undo/revert) is an absorbing halt. | v11 §3 |
| $\beta$ | $\mathbb{R}_{>0}$ | Halt-penalty rate. As $\beta\to\infty$, any $\mathrm{HUKLLA}(a)>0$ drives $e^{-\beta\mathrm{HUKLLA}}\to 0$. | new (v12) |
| $\mathrm{Khipu}_i(a)$ | $\{0,1\}$ | $i$-th receipt verification; 1 ⇔ `chain_verified=true`. The product is 0 if any receipt fails. | v11 §4 (YAWAR) |
| $\mathcal{A}$ | finite set | Bounded action space; $\lvert\mathcal{A}\rvert$ is **Bekenstein-bounded** by the context budget. | v11 §12 |

**Reading.** $\Lambda(x)$ is the context's standing trust scale. $\mathrm{Yuyay}_{13}(a)$ is
the conjunctive admission gate. The exponential is the **soft halt** — each fired tripwire
multiplies utility by $e^{-\beta}$. The Khipu product is the **hard provenance gate** — one
broken receipt zeroes the action. `P` then takes the `argmax` over the bounded $\mathcal{A}$.

## The four invariants

Each invariant has a `sorry`-tagged Lean theorem in `formulas/PuriqLean.lean`. None is claimed
proven; each is honestly stated as an open obligation per HR-4 (Zero-Bandaid).

### INV-1 — Halting safety
For $a$ with $\mathrm{HUKLLA}(a)\ge 1$ and $b$ with $\mathrm{HUKLLA}(b)=0$, $U_0(b)>0$, there
exists $\beta^*$ such that for all $\beta>\beta^*$, $U(a\mid x)<U(b\mid x)$. In the limit, a
STOP directive (T10) makes `argmax` never select a halted action. *(Lean: `puriq_halting_safety`.)*

### INV-2 — Λ-monotonicity preservation
Raising any context axis cannot lower $\Lambda(x)$; since $U(a\mid x)$ is $\Lambda(x)$ times a
non-negative action-only factor, the `argmax` is monotone in the context axis vector.
*(Lean: `puriq_lambda_monotone`.)*

### INV-3 — Khipu-chain integrity required for non-zero utility
$U(a\mid x)>0$ implies $\prod_i \mathrm{Khipu}_i(a)=1$. Contrapositive: any failed receipt
forces $U=0$, so a provenance-broken action can never be selected over a verified one.
*(Lean: `puriq_khipu_integrity`.)*

### INV-4 — Bekenstein bound on $\lvert\mathcal{A}\rvert$
$\lvert\mathcal{A}\rvert \le N_{\text{Bek}}(x)$, the v11 `bekenstein_cascade` bound. The
`argmax` is over a finite, decidable set; agency cannot enumerate an unbounded action space.
*(Lean: `puriq_bekenstein_bound`.)*

## The twelve sub-formulas

Every organ derives its sub-formula by (a) restricting $\mathcal{A}$, (b) re-weighting the 13
Yuyay axes, and/or (c) adding one organ-specific non-negative factor in $[0,1]$ that cannot
break any invariant. See [Anatomy + Organs](/anatomy/) for each organ's full derivation.

| SF | Organ | Extra factor | Anchor |
|----|-------|--------------|--------|
| SF-01 {#sf-01} | Yuyaq — cortex | $e^{-\gamma\mathrm{KL}}$ drift penalty | Pinsker / DPI |
| SF-02 {#sf-02} | Yuyay — heart | identity (the gate) | 13-axis AND |
| SF-03 {#sf-03} | Yawar — blood | $C(a)$ chain-link | SHA-256 chain |
| SF-04 {#sf-04} | Hukulla — immune | $e^{-\beta H}$, $\beta\gg0$ | Egyptian doubling |
| SF-05 {#sf-05} | Kallpa — wires | $B(a)$ Butler–Volmer budget | electrochemistry |
| SF-06 {#sf-06} | Khipu — DAG | Merkle / sum invariant | khipu sum-of-sums |
| SF-07 {#sf-07} | Lambda — spine | $\Lambda(x)$ geometric mean | A1–A4 |
| SF-08 {#sf-08} | OTel — nerves | $O(a)$ trace-continuity | W3C trace-context |
| SF-09 {#sf-09} | Kanchay — brand | $K(a)$ sacred-axis | T01/T02 |
| SF-10 {#sf-10} | Hatun — doctrine | $D(a)$ additivity | HR-3 / HR-7 |
| SF-11 {#sf-11} | Sumaq — designer | $S(a)$ honest-proof | status tags |
| SF-12 {#sf-12} | Killinchu — bridge | $G(a)$ geofence | Bekenstein / reachability |

## Honest labels (carried from v11 §9)

- **Λ-uniqueness is [Conjecture 1](/doctrine/v11-v12#conjecture-1), NOT a theorem** — it depends
  on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) plus a missing symmetry axiom. `P(x,t)`
  uses Λ as the canonical D2 aggregator; it does not assume Λ is the unique such aggregator.
- The Khipu receipt **signature** is **DSSE PLACEHOLDER** (Sigstore not wired into CI);
  $\mathrm{Khipu}_i(a)$ verifies the **hash chain**, not the signature, until signing lands.
- SLSA level remains **L1 (honest)**. "SLSA L3" is BANNED.

---

*Doctrine v12 (PURIQ layer) — additive over v11 LOCKED 2026-06-01 01:45 EDT. Authored by
Yachay. Quechua etymology cited to Wiktionary and érudit. Every obligation `sorry`-tagged,
never hidden. — NO BANDAID. NO mysticism.*
