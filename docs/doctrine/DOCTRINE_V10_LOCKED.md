# Doctrine v10 — LOCKED 2026-05-31 23:55 EDT

**Source:** Founder GitHub release screenshots (lutar-lean v18.0.0 HONESTY CORRECTION, ouroboros-thesis v18.0, Zenodo v18.0, org-card "What is honest right now", platform Codex-Kernel v1.0.0, vsp-otel v0.1.0) + canonical reproducibility counter run at c7c0ba17.
**Supersedes:** Doctrine v9 (DOCTRINE_V9_LOCKED_2026-05-31_2210.md) — that file's §4/§5/§9 numbers (456/6) and §2D Theorem-1 ruling are RETIRED.
**Authority:** Founder directive 2026-05-31: the founder's published GitHub release numbers are authoritative. A re-audit number that contradicts the founder's own published honest counter is, by definition, the wrong number.

---

## §0 — CRITICAL TRUTH REVISION (why v10 exists)

Doctrine v9 §4 locked **456 declarations / 6 sorries** from a re-audit. The founder then published GitHub release screenshots with an explicit **HONESTY CORRECTION** showing **749 / 14 / 163**, produced by the canonical reproducibility counter (`.github/scripts/lean_numbers.py`) run against the exact release. I re-ran that counter against the exact commit. **The founder is right. The re-audit was wrong** (it ran against a stale, divergent local clone at `f3ae580` using a restricted token set that excluded `abbrev/instance/structure/inductive/class`). Full evidence: `round2/full_reaudit_2026-05-31/PHASE1_NUMBER_RECONCILIATION.md`.

---

## §1 — LOCKED CANONICAL NUMBERS

**Produced by the canonical counter the founder cites in his HONESTY CORRECTION, at the exact canonical HEAD c7c0ba17 (lutar-lean tag `lutar-v18.0.0` / release `0086521`):**

| Metric | LOCKED v10 value | Source |
|--------|-----------------:|--------|
| **Declarations** | **749** | `lean_numbers.py` @ c7c0ba17 (theorem+lemma+def+abbrev+instance+structure+inductive+class) |
| **Unique axioms** | **14** | (15 raw, 1 dup — `sha256` declared twice) |
| **Raw axioms** | **15** | |
| **Sorries (total)** | **163** | raw `\bsorry\b` token count @ c7c0ba17 |
| **Sorries baseline** | **112** | non-Putnam |
| **Sorries Putnam** | **51** | `Lutar/Putnam/` |
| Policy gate modules (a11oy) | 46 | `*_gate.ts` count |
| Anchor formula gates | 44 | founder-screenshot canonical |
| MCP tools | 12 | Ouroboros canonical |
| Canonical HF Spaces | 7 | README + a11oy + amaru + sentra + vessels + rosie + uds-demo |

**Reconciliation of the 163 vs 168 discrepancy:** 163 is the count at tag time (c7c0ba17). The org card's "168" is the same corpus measured at a *later* main HEAD (PRs #135–#137 added disclosure sorries; current main 679d3d8 = 169 raw). Both are honest at their respective SHAs. **The LOCKED canonical for v10 is 163 @ c7c0ba17.** When citing live main, say "163 at tag `lutar-v18.0.0`; ~168 on current main (corpus moving)."

### Canonical 14 axiom names
`MomentSubGaussian` · `audit_reidemeister_invariance` · `canonicalReceipt` · `chromotopology_code_bijection` · `gleason_length_mod_8` · `klDivergence_nonneg` · `lambda_schur_concave_n_axis` · `lambda_stationary_unique` · `liu_hui_pi_converges` · `pinsker` · `r1_invariance` · `r2_invariance` · `sha256` · `sha256_collision_resistant` (15th raw = `sha256` dup).

---

## §2 — Λ UNIQUENESS IS A CONJECTURE (v9 §2D REVERSED)

**Status:** Λ uniqueness is a **Conjecture, NOT a closed theorem.**

**Evidence (source @ c7c0ba17):** `Lutar/Uniqueness.lean:120` — `theorem lutar_is_geomean ... := sorry -- CAUCHY_ND` (Aczel 1966 Thm 5.1; ~40h sprint). The result depends on the **open CAUCHY_ND sorry** plus a **missing symmetry axiom**. Org card confirms: "Λ uniqueness is currently a Conjecture, not a closed theorem — depends on CAUCHY_ND sorry and missing symmetry axiom."

**Canonical wording:** "**Conjecture 1 (Λ uniqueness)** — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) and a missing symmetry axiom." 

**RETIRED (do not use):** v9's "Theorem 1 — Λ Uniqueness (proved)". Any surface saying "Theorem 1" for Λ-uniqueness or "fully verified" uniqueness must be corrected to "Conjecture 1 (depends on CAUCHY_ND sorry)."

Discharge-route examples (honest "open obligation" framing): `Lutar/Uniqueness.lean:120` (CAUCHY_ND), `Lutar/TwoWitness.lean:163`, `Lutar/HUKLLA/SBOMProvenance.lean`.

---

## §3 — AXIOM SEMANTICS A2 / A4 (corrected; v3 proofs do NOT carry over)

From `Lutar/Axioms.lean` @ c7c0ba17:
- **A2 = `IsHomogeneous`** — Positive homogeneity (degree 1): `∀ c x, Λ(c·x) = c·Λx`. **NOT "zero-pinning."**
- **A4 = `IsBounded`** — Bounded by max axis: `∀ x, Λ x ≤ Finset.univ.sup' _ x`. **NOT "page-curve concavity."**
- **v3 Zenodo deposit (10.5281/zenodo.19983066) proofs do NOT carry over** to current A2/A4 — confirmed by lutar-lean PR #136 ("disclose A2/A4 semantic drift from v3 deposit to current v14"). Never claim the v3 proofs validate the current A2/A4.

---

## §4 — WIRES STATUS (honest)

| Wire | Path | Status |
|------|------|--------|
| **Wire B** | a11oy ↔ sentra immune | **LIVE on main** |
| **Wire C** | a11oy ↔ rosie receipt stream | **LIVE on main** |
| **Wire D** | W3C `traceparent` across the mesh | **NOT YET IMPLEMENTED** — do NOT claim |

**Canonical wording:** "Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are LIVE on main. Wire D (W3C traceparent across the mesh) is not yet implemented." (Upgrades v9 §2F which said Wire C was "half-wired" — it is now LIVE.)

---

## §5 — SLSA, RECEIPTS, COMPLIANCE (honest)

- **SLSA: Honest L1** — was previously claimed as L3; corrected in platform **PR #235**. **"SLSA L3" is BANNED.** Always say "SLSA L1 (honest)."
- **Receipts:** DSSE envelopes ship from the **amaru tick endpoint today** (live). **Sigstore CI signing is PENDING** — signature fields must be honestly labeled **"PLACEHOLDER — signing not yet wired into CI."** Never present placeholder signatures as real.
- **Compliance:** Aligned with **EU AI Act Article 12** (record-keeping for high-risk AI systems) and **NIST AI RMF (MANAGE function)**.

---

## §6 — THESIS v18 / ZENODO v18 (the real v18)

- **Real v18 PDF:** 206 pages, 1.2 MB, SHA256 `579288b0e0ce628d…`, commit **855ae52** (verified), tag **paper-v18-1.0.0**. Published via ouroboros-thesis GitHub release v18.0 (Latest, 2026-05-30).
- **Zenodo v18 mislabel:** the v18 Zenodo deposit had a **v17 stub attached by error**. The founder already corrected this via the GitHub release ("Real v18 PDF replaces the v17 stub previously attached to the v18 Zenodo deposit by error"). When citing v18, use the GitHub release / 206-page / SHA256 `579288b0…` / commit 855ae52 as canonical.
- **Zenodo v18.0 "Multi-track Substrate Expansion"** (Published 2026-05-28, version paper-v18-1.0.0): consolidated record for v17.1–v18.12 delta graft sessions under Doctrine v6; 16 tracked community + frontier integration tracks 2026-05-28 to present.

### 16 v17.x → v18.x tracks (canonical list)
v17.x: **the-four** (v17.1), **a11oy-code formal proofs** (v17.1.1), **GraphLambda + GNN governance head** (v17.2), **UDS air-gap drone operations** (v17.3), **standardgalactic mathematics**; v18.x: frontier architecture and observability (vsp-otel Λ-signed OTel exporter, etc.). The full ladder spans v17.1 → v18.12.

---

## §7 — UN-BANNED in v10 (ADDITIVE to v9; evidence = founder GitHub screenshots / platform source)

These are confirmed real and are UN-BANNED (in addition to everything v9 un-banned):

| Token | Evidence |
|-------|----------|
| **GraphLambda** | Zenodo v18 track v17.2 (GraphLambda + GNN governance head) |
| **GNN governance head** | Zenodo v18 track v17.2 |
| **Dresden-Venus emulator** | platform Codex-Kernel v1.0.0 (emulator + canonical payload) |
| **codex-kernel** | platform `packages/codex-kernel` — pure-TS, zero runtime deps |
| **lean-payload normalizer** | Codex-Kernel `src/cli/normalize.ts` (SZL governed-ops payload + lean-payload normalizer) |
| **IsHomogeneous** | `Lutar/Axioms.lean` A2 |
| **IsBounded** | `Lutar/Axioms.lean` A4 |
| **the-four** | Zenodo v18 track v17.1 |
| **standardgalactic mathematics** | Zenodo v18 track |
| **governed-loop primitive** | Codex-Kernel v1.0.0 ("Replay-grade governed-loop primitive for AI agents") |
| **hard-stop validators** | Codex-Kernel (hard-stop validators + deterministic replay verifier) |

---

## §8 — STILL BANNED (unchanged from v9 + reinforced)

| Token | Reason |
|-------|--------|
| **Jarvis** | Legacy identity, 0 hits in 3-source audit |
| **Bo11y** | Legacy identity |
| **Bolly** | Legacy identity |
| **Computacenter** | Founder hard rule ("our secret") |
| **"45 gates"** | Never real; real is 44 (anchor) / 46 (policy modules) |
| **"SLSA L3"** | FALSE — honest level is L1 (platform PR #235). Must always be L1. |
| **"zero sorry / zero open axioms"** | FACTUALLY FALSE — 163 sorries, 14 axioms. The founder's own HONESTY CORRECTION retired this claim. |
| **"fully verified" (unscoped)** | Only permitted scoped to a specific zero-sorry lemma. |
| **Bare "Mythos" (internal)** | Rename rule: internal → `Hatun-Willay`. External Anthropic/OpenMythos citations OK. |
| **"11 MCP tools" / "14 MCP tools"** | Real is 12 |
| **Static hardcoded SHAs without CI refresh** | Use `main` refs unless CI auto-updates |

---

## §9 — STALE-NUMBER CORRECTION MAP (for Space sweeps)

When sweeping any live surface, replace:
- `456` → `749` (declarations)
- `6` (as sorry count) → `163` (sorries)
- `168` (as locked sorry count) → `163` at tag, note "~168 on moving main"
- `"fully verified"` (unscoped) → `"163 sorries tracked honestly"`
- `"Theorem 1"` (Λ-uniqueness) → `"Conjecture 1 (depends on CAUCHY_ND sorry)"`
- any `"SLSA L3"` → `"SLSA L1 (honest)"`
- A2 `"zero-pinning"` → `"IsHomogeneous (positive homogeneity deg 1)"`
- A4 `"page-curve concavity"` → `"IsBounded (bounded by max axis)"`

---

## §10 — "WHAT IS HONEST RIGHT NOW" BLOCK (mirror the org card on every Space)

Every public Space must carry this honest-disclosure block:

> **What is honest right now (lutar-lean @ tag `lutar-v18.0.0` / c7c0ba17):**
> - **749 declarations, 14 unique axioms (15 raw, 1 dup), 163 tracked sorries** (112 baseline + 51 Putnam). `lake build` clean.
> - **Λ uniqueness is a Conjecture, not a closed theorem** — depends on the open CAUCHY_ND sorry (`Uniqueness.lean:120`) + a missing symmetry axiom.
> - **Wires:** Wire B (a11oy↔sentra immune) and Wire C (a11oy↔rosie receipt stream) are **LIVE on main**. Wire D (W3C traceparent across the mesh) is **NOT YET IMPLEMENTED**.
> - **SLSA: L1 (honest)** — was previously mis-claimed as L3; corrected in platform PR #235.
> - **Receipts:** DSSE envelopes ship from the amaru tick endpoint today. **Sigstore CI signing is PENDING** — signature fields are honestly labeled "PLACEHOLDER — signing not yet wired into CI."
> - Aligned with **EU AI Act Article 12** and **NIST AI RMF (MANAGE)**.

---

## §11 — OPERATIONAL RULES (carry-forward)

- **HR-1: HF admin direct push always** via `HfApi.create_commit()`. NEVER GitHub Actions for HF sync.
- **HR-2: Mythos → Hatun-Willay** rename (internal); external Anthropic/OpenMythos citations OK.
- **HR-3: ADDITIVE only.** Never delete founder content. Founder-locked surfaces (banner, 5 hero avatars, animated emojis) UNTOUCHED.
- **HR-4: ZERO BANDAID.** No fake/placeholder values presented as real; PLACEHOLDER must be labeled.
- **HR-5: IP-HOLD PRs untouched** — a11oy#57, amaru#46, sentra#45.
- **HR-6: Numbers come from the canonical counter, not memory.** Re-run `lean_numbers.py` before citing.
- **HR-7: A founder-published number beats any internal re-audit.** If they conflict, audit the re-audit.

---

## §12 — CHANGE LOG FROM v9

| Item | v9 ruling | v10 ruling | Evidence |
|------|-----------|------------|----------|
| Lean declarations | 456 (re-audit) | **749** | `lean_numbers.py` @ c7c0ba17; founder release |
| Tracked sorries | 6 (re-audit) | **163** (112+51) | same |
| Unique axioms | 14 | **14 (15 raw, 1 dup)** | same |
| Λ uniqueness | "Theorem 1 (proved)" | **Conjecture 1 (open CAUCHY_ND sorry)** | `Uniqueness.lean:120`; org card |
| A2 axiom | (unspecified) | **IsHomogeneous (pos. homogeneity deg 1)** | `Axioms.lean` |
| A4 axiom | (unspecified) | **IsBounded (bounded by max axis)** | `Axioms.lean` |
| Wire C | "half-wired (receiver in flight)" | **LIVE on main** | org card |
| Wire D | (not addressed) | **NOT YET IMPLEMENTED** | org card |
| SLSA | "L1 honest" | **L1 honest (reinforced; L3 banned, platform PR #235)** | org card |
| codex-kernel / Dresden-Venus / GraphLambda / GNN head / the-four / governed-loop / hard-stop validators / lean-payload normalizer / standardgalactic | (not addressed) | **UN-BANNED** | platform Codex-Kernel v1.0.0; Zenodo v18 tracks |
| v18 thesis | (not pinned) | **206 pp, SHA256 579288b0…, commit 855ae52, tag paper-v18-1.0.0** | ouroboros-thesis release v18.0 |

---

— Yachay (Perplexity Computer Agent), under CTO authority
— Doctrine v10 LOCKED 2026-05-31 23:55 EDT
