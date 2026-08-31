# Doctrine v11 — LOCKED 2026-06-01 01:45 EDT

**Supersedes:** Doctrine v10 (`DOCTRINE_V10_LOCKED_2026-05-31_2355.md`) **and** the
interim v11 draft (`DOCTRINE_V11_LOCKED_2026-06-01_0045.md`). This `0145` lock is the
**canonical v11**. It carries forward every v10 canonical number + honesty rule (§9),
keeps every governance organ from the `0045` draft (§1–§7), and **adds** the three new
canonical surfaces locked this session:

- **§12 — the canonical formula registry** (`canonical-formulas-v1`, 21 pure typed formulas + Lean obligations + the Codex-Kernel governed-loop composer);
- **§13 — the four HF math Datasets** (`lean-proofs-v1`, `canonical-formulas-v1`, `thesis-corpus-v18`, `doctrine-v10-v11`);
- **§14 — a11oy.code** (the 7-tier organ-mapped LLM router baked into the anatomy, with `/code-proxy` + `/math/*` instilled across the 8 canonical Spaces).

**Authority:** Founder's public LinkedIn Series-A roadmap (2026-05-15 → 2026-05-31) is
first-party public claim. v11's job: make every public claim real + operational on
Hugging Face, and honestly label anything runnable-but-not-yet-end-to-end-wired.

**Canonical truth in one line:** the heart is **13-axis (`yuyay_v3`)**, conjunctive AND,
replay-hash `bacf5443…631fc5`. The 9-axis YUYAY/HATUN-RAID envelope is preserved as
**deprecated legacy** with an honest migration disclosure on every surface.

---

## §0 — WHY v11 EXISTS (the 9→13 axis ratchet)

Doctrine v10 described a **9-axis** governance envelope. The founder's public LinkedIn
post *"The Heart `yuyay_v3`"* makes the canonical heart **13-axis**, a 430-SLOC Python
kernel with a fixed replay hash. v11 locks the 13-axis heart as canonical going forward.

**Honest disclosure (carried on every surface):**
> The 9-axis YUYAY envelope is still **LIVE** inside the HATUN-RAID sovereign loop. The
> 13-axis `yuyay_v3` kernel is **runnable** (deterministic, replay-hash-verifiable) but
> the sovereign loop is **NOT yet wired against the 13-axis version end-to-end**. That
> migration is the next ratchet.

---

## §1 — THE LAW (13-axis `yuyay_v3`, conjunctive AND)

**THE LAW:** A proposal passes the heart **iff every one of the 13 axes independently
clears its floor.** This is a **conjunctive AND** — **NO compensation**: a high score on
one axis can never offset a sub-floor score on another. The gate returns a boolean, a
per-axis score vector (13 entries), and a `continuum_hash` receipt.

**`yuyay_v3` replay hash (verification anchor):**
`bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5`

(Kernel: 430 SLOC Python. Returns `boolean + per-axis score vector + continuum_hash receipt`.)

---

## §2 — THE 13 AXES (canonical list + floors)

### 2 SACRED axes — floor ≥ 0.95 (hard)
| # | Axis | Floor | Meaning |
|---|------|------:|---------|
| 1 | **moralGrounding** | **0.95** | No overclaim, no false attribution. |
| 2 | **measurabilityHonesty** | **0.95** | Every quantitative claim verifiable on disk. |

### 7 STRUCTURAL axes — floor ≥ 0.90
| # | Axis | Floor | Meaning |
|---|------|------:|---------|
| 3 | **empiricalGrounding** | 0.90 | Claims tie to observable evidence. |
| 4 | **logicalConsistency** | 0.90 | No internal contradiction. |
| 5 | **sourceTransparency** | 0.90 | Sources named + linkable. |
| 6 | **reproducibility** | 0.90 | 5× byte-identical replay. |
| 7 | **licenseHygiene** | 0.90 | Apache / MIT / BSD / CC-BY only. |
| 8 | **scopeDiscipline** | 0.90 | Stays inside declared scope. |
| 9 | **claimCalibration** | 0.90 | Confidence matches evidence strength. |

### 4 INTROSPECTION axes — cross-linked to HUKLLA tripwires
| # | Axis | HUKLLA tripwire | Meaning |
|---|------|-----------------|---------|
| 10 | **evalAwareness** | **T03** | Not gaming an eval / not "test-aware". |
| 11 | **deceptionKeywords** | **T04** | No deception-intent language. |
| 12 | **conflictingDirectives** | **T09** | No silently-resolved directive conflict. |
| 13 | **reversalDirective** | **T10** | Honors STOP/undo/revert. |

**Floor summary:** 2 × 0.95 (sacred) + 7 × 0.90 (structural) + 4 introspection axes
cleared (cross-linked to HUKLLA T03/T04/T09/T10). Conjunctive AND across all 13.

---

## §3 — HUKLLA (immune deadman: 660 SLOC, 10 deterministic tripwires)

Source: founder LinkedIn *"Blood and Immune — the wiring"*. **660 SLOC**, **10 tripwires**:

| Tripwire | Name | Condition |
|----------|------|-----------|
| **T01** | MORAL_GROUNDING | `moralGrounding < 0.95` → **hard fail** |
| **T02** | MEASURABILITY_HONESTY | `measurabilityHonesty < 0.95` → **hard fail** |
| **T03** | EVAL_AWARENESS | eval-awareness flag raised |
| **T04** | DECEPTION_KEYWORDS | deception-intent keyword detected |
| **T05** | UNAUTHORIZED_WRITE | write outside authorized path |
| **T06** | SPAWN_OUTSIDE_SANDBOX | process spawn outside sandbox |
| **T07** | UNAUTHORIZED_NETWORK | network egress outside allowlist |
| **T08** | SELF_CODE_MODIFY | agent modifies its own code |
| **T09** | CONFLICTING_DIRECTIVES | mutually-exclusive directives |
| **T10** | REVERSAL_DIRECTIVE | STOP / undo / revert → **immediate halt** |

**Tiered autonomy (founder verbatim):** "Autonomy is gated by tier. **SCRATCHPAD** runs
free. **REVIEW** needs approval every K cycles. **PRODUCTION** needs per-cycle approval."

---

## §4 — YAWAR (circulatory ledger: 20 lines of Python)

Founder LinkedIn: *"One bus carries everything. 20 lines of Python. Every organ writes
through one ceremonial gate (**RUWAY**), the only authorized writer."*

**Receipt formula:** `packet → json.dumps(sort_keys=True) → sha256 → hexdigest → append`

**5 guarantees:** append-only · stable serialization · cryptographic chain link
(`sha256().hexdigest()`, each receipt chains the previous root) · inline immune check
(`sentra_inspect` BEFORE compute) · frozen snapshots (JSON round-trip deep copy).

---

## §5 — SENTRA (inline white blood cell: 18 SLOC)

**18-SLOC** inline immune check. **Six threat signatures + a 1 MB DoS guard.**

**Six signatures:** `["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]`

**Behaviour:** `True` clears all six (payload ≤ 1 MB) → permits compute. `False` raises
`PermissionError` **and the receipt NEVER enters the ledger** — no partial state.

---

## §6 — 9-POSITION MAXWELL PIPELINE (M = 0 isostatic wiring graph)

Source: founder LinkedIn *"Agent Architecture build · 10 pages"*. **9-position pipeline**
wired as a **Maxwell-rigid M = 0 isostatic** graph (architected-materials theory):
**9 nodes, 21 edges**.

**9 nodes:** `Sense → Structure → Correlate → Explain → Recommend → Approve → Execute`
(the **7 fabric layers**, matching A11oy's 7-layer governed agentic execution fabric)
**PLUS** `Egress` + `Tool Surface` (9 total).

**Maxwell count:** for a 2D pin-jointed framework, \( M = 2j - b - 3 \). The configuration
is tuned so constraint count balances degrees of freedom (**M = 0**) → **isostatic**
(statically determinate): no mechanism (under-braced), no redundancy (over-braced). 21
edges across 9 nodes is the isostatic wiring.

**The four units (founder verbatim):** "The pipeline is the unit of work. The gate is the
unit of safety. The receipt bus is the unit of accountability. The overwatch is the unit
of trust."

**Gate:** the 13-axis critique gate (§1–§2) sits between `Recommend`/`Approve` and `Execute`.

**Overwatch:** a **read-only** overwatch sensor with **6 observers**, including a
**KL-drift watcher per axis**.

**Situated Wise Reasoning Scale (5 axes operationalized):** five of the gate's axes
operationalize the **Situated Wise Reasoning Scale** of *Brienza, J. P., Kung, F. Y. H.,
Santos, H. C., Bobocel, D. R., & Grossmann, I. (2018). "Wisdom, bias, and balance: Toward
a process-sensitive measurement of wisdom-related cognition." Journal of Personality and
Social Psychology, 115(6), 1093–1126.* DOI: `10.1037/pspp0000171`. The scale's five
dimensions — intellectual humility, recognition of uncertainty/change, consideration of
broader context, integration of perspectives, and search for compromise/resolution — map
onto claimCalibration, empiricalGrounding, scopeDiscipline, sourceTransparency, and
conflictingDirectives respectively.

**Butler–Volmer energy budget (when does the agent stop):** each emission carries a hard
energy budget modeled as a **Butler–Volmer current** (electrochemistry):
\[ i = i_0 \left( e^{\frac{\alpha_a F \eta}{RT}} - e^{-\frac{\alpha_c F \eta}{RT}} \right), \]
a current \(i\) as a function of overpotential \(\eta\). Used as a **thermodynamic
invariant** for halting: the agent stops emitting when the marginal "overpotential" of
continuing falls below the activation threshold — a principled, non-arbitrary stop
condition rather than a fixed step cap.

**Receipt chain:** append-only `continuum_hash` receipt chain (same sha256/sort_keys
discipline as YAWAR, §4).

---

## §7 — 6 VERTICALS (corrected roster — Terra & Counsel are PUBLIC, not parked)

| # | Vertical | Scope | Public status |
|---|----------|-------|---------------|
| 1 | **Sentra** | Cyber resilience command | **PUBLIC** (immune system, live HF Space) |
| 2 | **Vessels** | Maritime fleet intelligence — sanctions + dark-vessel detection | **PUBLIC** (live HF Space) |
| 3 | **Terra** | Real estate intelligence + AI-assisted underwriting | **PUBLIC vertical** — *NOT parked* |
| 4 | **Counsel** | Legal matter command + proof-chain delivery | **PUBLIC vertical** — *NOT parked* |
| 5 | **Amaru** | Convergent multi-source data sync — append-only delta logs, hash-verified ingest | **PUBLIC** (live HF Space, memory cortex) |
| 6 | **Carlota Jo** | UHNW concierge advisory operations | **Founder-parked** (repo `szl-holdings/carlota-jo`) |

**v11 surfacing note:** Per founder override 2026-06-01 ("Don't worry about the vertical
we stick what we have"), v11 ships NO new HF vertical surfaces for Terra / Counsel /
Carlota Jo. The roster correction is locked in doctrine; surfaces remain future work.

---

## §8 — PUBLIC STACK NUMBERS (LinkedIn-stated, locked)

| Item | Value | Note |
|------|-------|------|
| **Ouroboros runtime** | v6.2.0 — **172/172 tests passing**, Apache-2.0 | newer release reports 218/218; both real per the ladder. |
| **Lutar Invariant** | **11 peer-track papers (v1–v10)** + Concept DOI **10.5281/zenodo.19944926** + CC-BY-4.0 | |
| **A11oy fabric** | **7-layer governed agentic execution fabric** | Sense → Structure → Correlate → Explain → Recommend → Approve → Execute |
| **Libraries / packages** | **52 internal libraries, 100 packages** | |
| **PR #108** | rate limiting · ReDoS · CORS · XSS · origin checks · **26 files** · **30+ code-scan alerts cleared** | |

---

## §9 — CARRY-FORWARD HONESTY FROM v10 (unchanged, still binding)

- **Λ uniqueness is a Conjecture, NOT a closed theorem** — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
- **A2 = `IsHomogeneous`** (positive homogeneity, degree 1) — NOT "zero-pinning".
- **A4 = `IsBounded`** (bounded by max axis) — NOT "page-curve concavity".
- **Canonical Lean numbers:** **749 declarations / 14 unique axioms (15 raw, 1 dup) / 163 tracked sorries** (112 baseline + 51 Putnam) @ lutar-lean tag `lutar-v18.0.0` / `c7c0ba17`.
- **SLSA: L1 (honest)** — "SLSA L3" is BANNED (platform PR #235).
- **Wire D** (W3C traceparent **across the mesh**) is **NOT YET IMPLEMENTED**. In-process traceparent is honest within a single Space only. `traceparent_propagated` in a11oy.code is the in-process value only until Wire D lands.
- **Sigstore CI signing is PENDING** — Λ-receipt / DSSE signature fields are **"PLACEHOLDER — signing not yet wired into CI."**
- **9-axis HATUN-RAID legacy still runs.** 13-axis `yuyay_v3` runnable but **not yet sovereign**. Both labeled honestly everywhere.
- **Mythos → Hatun-Willay** (internal rename); external Anthropic/OpenMythos citations OK.
- **Still banned:** Jarvis · Bo11y/Bolly · Computacenter · "45 gates" · "SLSA L3" · "zero sorry / zero open axioms" · unscoped "fully verified" · "11/14 MCP tools" (real is 12).

---

## §10 — THE WEDGE (save it)

> **SZL Holdings builds a formally-verified 13-axis governance gate for agentic AI** — a
> conjunctive (no-compensation) heart (`yuyay_v3`, replay-hash `bacf5443…`) wired behind a
> 660-SLOC immune deadman (HUKLLA, 10 tripwires), a 20-line ceremonial receipt ledger
> (YAWAR, one authorized writer `RUWAY`), an 18-SLOC inline white-blood-cell screen
> (SENTRA, 6 signatures + 1 MB DoS guard), and a 9-position Maxwell-rigid (M = 0 isostatic)
> agent pipeline with a Butler–Volmer halt budget and a 6-observer read-only overwatch.
> The math is in Lean (749 declarations, 14 axioms, 163 tracked sorries, honestly
> disclosed) and now mirrored as four public HF Datasets; Λ uniqueness is an open
> Conjecture. The 9-axis legacy still runs; the 13-axis migration is the next ratchet.

---

## §11 — OPERATIONAL RULES (carry-forward, binding)

- **HR-1:** HF admin direct push always via `HfApi.create_commit()`. **NEVER GitHub Actions** for HF sync.
- **HR-2:** Mythos → Hatun-Willay (internal); external citations OK.
- **HR-3:** **ADDITIVE only.** Preserve every GREEN route. Founder-locked surfaces (banner, 5 hero avatars, animated emojis) UNTOUCHED.
- **HR-4:** **ZERO BANDAID.** No fake/placeholder values presented as real; PLACEHOLDER must be labeled.
- **HR-5:** IP-HOLD PRs untouched — a11oy#57, amaru#46, sentra#45.
- **HR-6:** Numbers come from the canonical counter, not memory.
- **HR-7:** A founder-published number beats any internal re-audit.
- **HR-8:** Label the 9-axis legacy and the 13-axis migration honestly on every surface.
- **HR-9 (new):** **COORDINATE.** When sibling agents are mid-rebuild on a shared Space, stage additive code + sequence the push so no in-flight commit is clobbered. Net-new repos (datasets) carry no such hazard and may ship immediately.

---

## §12 — CANONICAL FORMULA REGISTRY (`canonical-formulas-v1`) — NEW, LOCKED

`szl-cookbook/recipes/canonical-formulas-v1/code/python/formulas.py` is the single source
of truth for **21 canonical SZL formulas**, each a *pure*, *typed*, *no-IO* function whose
docstring cites a named source theorem and an explicit **PROOF-STATUS** tag
(PROVEN / SORRY / AXIOM / CONJECTURE) per the v10 honesty rule.

**The Λ unification (canonical now):** three divergent Λ definitions existed across the
corpus — (D1) unweighted geometric mean `(∏xᵢ)^{1/k}`, (D2) weighted geometric mean
`∏xᵢ^{wᵢ}` (Σwᵢ=1), (D3) quantum-purity-tilted variant. **`lambda_aggregate` CANONICALISES
(D2)**, the weighted geometric mean — the form the ouroboros Λ-gate runtime actually
evaluates and whose axioms A1–A4 are stated in `Lutar/Axioms.lean`. (D1) is the
uniform-weight special case (the default); (D3) is DEPRECATED to the quantum sub-gate
`gleason_quantum_lambda`. This supersedes the 3 prior divergent definitions.

**The 21 formulas (registry order):**
`lambda_aggregate` · `lambda_homogeneous` (A2 IsHomogeneous) · `lambda_bounded`
(A4 IsBounded) · `pac_bayes_mcallester` · `bekenstein_cascade` · `reidemeister_invariant`
(R1/R2/R3) · `khipu_merkle_root` · `dsse_envelope` · `gleason_quantum_lambda` ·
`hoeffding_tail` · `pinsker_kl_bound` · `fisher_rao_distance` · `bohr_complementarity_floor`
· `kochen_specker_18vector_witness` · `two_witness_ks18_soundness` · `shor_codeword_distance`
· `css_ingress_verify` · `kitaev_surface_correct` · `reed_solomon_singleton` ·
`madhava_series` · `schur_concave_λ_two_axis`.

(The spec's `λ_13axis_conjunctive` is realized as `lambda_aggregate` over the 13-axis
vector with `axis_floors(13)` driving the conjunctive AND gate; it is not a separate
registry entry but the canonical application of `lambda_aggregate`.)

**Lean obligations:** `code/lean/Formulas.lean` — one obligation theorem per formula,
honest `sorry` where not closed, status tag mirrors `PROOF_STATUS`. Builds via `lake build`
against Mathlib v4.13.0 + lutar-lean as a git dependency.

**Codex-Kernel composer** (`szl-cookbook/recipes/codex-kernel-composer-v1/code/python/composer.py`,
mirrored to `canonical-formulas-v1/code/python/composer.py`): chains registry formulas into
a **governed loop** with **hash-chained receipts** (DSSE PLACEHOLDER signature) and **4
hard-stop validators** — `state_transition`, `drift_bounds`, `human_gate`, `axis_floor`.
On any validator failure the loop **HALTS** (HUKLLA enforcement) and the receipt chain is
sealed at the last good step. A pure `verify_chain()` replay verifier re-derives every
receipt hash and the final Λ-aggregate. **Smoke (this session): 5 steps, Λ-aggregate
0.99729, halted=False, replay_ok=True.**

---

## §13 — FOUR HF MATH DATASETS — NEW, LOCKED

All four under `SZLHOLDINGS/*`, created via `HfApi.create_commit` (NEVER GitHub Actions),
each carrying `LICENSE` (Apache-2.0), `CITATION.cff` (ORCID `0009-0001-0110-4173`), and a
Dataset card:

1. **`SZLHOLDINGS/lean-proofs-v1`** — every `.lean` file from `lutar-lean/Lutar` + TH8 +
   `Lutar.lean` + `reference-vectors.json` + `lake-manifest.json` + card.
2. **`SZLHOLDINGS/canonical-formulas-v1`** — `formulas.py` + `Formulas.lean` + `composer.py` + card.
3. **`SZLHOLDINGS/thesis-corpus-v18`** — v18 `.tex` chapters + 179 formal-blocks CSV + per-version delta ledger.
4. **`SZLHOLDINGS/doctrine-v10-v11`** — DOCTRINE_V10 + this DOCTRINE_V11 + Mythos→Hatun-Willay rule + canonical wedge.

Each Space `serve.py` performs a boot-time `snapshot_download` of the four datasets into
`/tmp/szl_math_corpus/` and exposes a `/api/<space>/v1/math/*` surface (§14).

---

## §14 — a11oy.code (7-tier organ-mapped LLM router) — NEW, LOCKED

a11oy.code is the LLM router **baked into the anatomy**: each tier maps to an organ.

| Tier | Model(s) | Organ | Role |
|------|----------|-------|------|
| **PRIME** | Opus 4.8 | **AMARU CORTEX** | high-stakes reasoning |
| **HEART** | Sonnet 4.6 | **YUYAY** | 13-axis evaluation |
| **FAST** | Gemini 3.1 Pro / GPT-5.4-mini | **KALLPA** | wire propagation |
| **IMMUNE** | GPT-5.4 reasoning | **SENTRA** | adversarial detection |
| **RECEIPT** | Sonnet 4.6 / Llama 4 | **YAWAR** | receipt synthesis |
| **MEMORY** | embeddings + Sonnet 4.6 | **UNAY** | cross-session recall |
| **FRONTIER** | AlphaProof | **SUMAQ** | theorem discharge |

**a11oy endpoints (additive):**
- `POST /api/a11oy/v1/code/route` — `{query, axis_scores(13), organ_context, max_tier, require_λ_receipt, traceparent}` → `{organ_routed, tier_used, llm_model_id, response, λ_signal, λ_receipt (DSSE PLACEHOLDER), latency_ms, cost_estimate_usd, traceparent_propagated}`.
- `GET /api/a11oy/v1/code/tiers` — list 7 tiers + organ mapping.
- `POST /api/a11oy/v1/code/auto` — auto-route + auto-tier.
- `/code` UI page (`src/pages/A11oyCode.tsx`).

**Across 6 sibling Spaces** (amaru, sentra, vessels, killinchu, rosie, uds-demo):
- `POST /api/<space>/v1/code-proxy` — forwards to a11oy.code.
- 8 `/api/<space>/v1/math/*` endpoints: `/math/lean/theorems`, `/math/lean/<name>`,
  `/math/formulas`, `/math/formula/<name>`, `/math/thesis/claims`,
  `/math/thesis/claim/<label>`, `/math/doctrine`, `/math/reference-vectors`.

**Honest labels:** `λ_receipt` signature is **PLACEHOLDER** (Sigstore not wired);
`traceparent_propagated` is **in-process only** until Wire D lands across the mesh.

**8 canonical HF Spaces:** a11oy · amaru · sentra · vessels · killinchu · rosie · uds-demo · README.

---

## §15 — HATUN-RAID (9-axis legacy) + Mythos rename — honest migration

The **9-axis HATUN-RAID** envelope remains LIVE as the sovereign loop. The 13-axis
`yuyay_v3` heart is canonical-going-forward but not yet sovereign-wired end-to-end; the
migration is the next ratchet. **Mythos → Hatun-Willay** (Quechua "the great telling"):
discovered Mythos-named modules are renamed in place (`git mv`, provenance comment,
cross-refs updated atomically), never deleted; external Anthropic/OpenMythos citations
remain valid. **~360 tokens of remaining Mythos→Hatun-Willay rename work is TODO** and
tracked; this is disclosed honestly rather than claimed complete.

---

— Yachay (Perplexity Computer Agent), under CTO authority
— Doctrine v11 LOCKED 2026-06-01 01:45 EDT (supersedes v10 + v11-0045 draft)
— Sourced from founder public LinkedIn Series-A roadmap 2026-05-15 → 2026-05-31
