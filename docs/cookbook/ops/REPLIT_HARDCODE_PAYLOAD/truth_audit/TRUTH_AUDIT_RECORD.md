# Doctrine V6 Truth-Audit Record

**Date:** 2026-05-16
**Operator:** Stephen P. Lutar Jr. — stephen@szlholdings.com — ORCID 0009-0001-0110-4173
**Reviewer pods:** PhD Dev, PhD ML, PhD Math, PhD Systems (4 parallel subagents, evidence-only, read-only)
**Scope:** ouroboros, ouroboros-thesis, lutar-lean, sentra, vsp-otel, agi-forecast, .github

This record names every defect found, where it is documented, and what GitHub PR comment carries the public correction.

---

## Critical defects (block Series A messaging until resolved)

### D1 — "sorry-count = 0" claim is false (severity: high)

**Claim location:** ouroboros-thesis arXiv v2 abstract (PR #44)
**Reality:** 4 unproven `sorry` positions on `lutar-lean@main`:

| File | Line | Theorem |
|------|------|---------|
| `Lutar/Bound.lean` | 25 | `Λ_le_max` |
| `Lutar/Bound.lean` | 30 | `min_le_Λ` |
| `Lutar/Uniqueness.lean` | 36 | `lutar_unique` |
| `Lutar/Uniqueness.lean` | 42 | `lutar_is_geomean` |

Plus 2 `sorry` + 2 `admit` in `Lutar/DoctrineV3/{Measurability,Moral}*.lean` (mix of in-prose + structural — needs follow-up).

**Public correction:**
- [lutar-lean#18 comment](https://github.com/szl-holdings/lutar-lean/pull/18#issuecomment-4467391875)
- [ouroboros-thesis#44 comment](https://github.com/szl-holdings/ouroboros-thesis/pull/44#issuecomment-4467393182)

**Source:** `phd_pods/math_pod_report.md` §"Sorry Census"

---

### D2 — PR #18 "closed 7 sorries" is uncompiled scaffolding (severity: high)

**Claim:** lutar-lean PR #18 title — "feat(th8): close 7/9 sorries"
**Reality:** All 7 "closed sorries" live in `TH8/lean_v2/`. The `lakefile.lean` library root is `lean_lib «Lutar»` rooted at `Lutar/`. `TH8/` is **not in the build**. `lake build` never touches those files. The PR's green CI confirms file structure only; it does not confirm proof correctness.

Of the 7 closures, Math pod flagged:
- S04 (`at_most_one_consume`) — hypothesis-padded skeleton
- S05 (`TH8a`) — hypothesis-padded skeleton
- S08 (`TH8_C3`) — trivially proved from a pathological hypothesis asserting all natural numbers are equal

**Public correction:** [lutar-lean#18](https://github.com/szl-holdings/lutar-lean/pull/18#issuecomment-4467391875)

**Source:** `phd_pods/math_pod_report.md` §"PR #18 Misrepresentation"

---

### D3 — `sha256_inj` axiom is mathematically false (severity: high)

**Location:** `TH8/lean_v2/LinearReceipt.lean` (PR #18)
**Declaration:**
```lean
axiom sha256_inj : ∀ a b, sha256 a = sha256 b → a = b
```
**Reality:** SHA-256 is a 256-bit finite-output hash. By pigeonhole, it is not injective. This axiom is **provably inconsistent with classical arithmetic on naturals**. Must be recast as a computational hypothesis (collision-resistance against polynomial-time adversaries), not a mathematical axiom.

**Public correction:** [lutar-lean#18](https://github.com/szl-holdings/lutar-lean/pull/18#issuecomment-4467391875)

**Source:** `phd_pods/math_pod_report.md` §"Non-Mathlib Axioms"

---

### D4 — Lean `Λ` ≠ production `Λ` (severity: high)

**Lean side:** `Lutar/Invariant.lean` defines `Λ` as a **geometric mean** parameterized by `k`.
**Production side:** `lambda-gate/src/gate.ts:51` uses a **conjunctive AND gate**:
```ts
const pass = scores.every((s, i) => s >= thresholds[i]);
```

The 9-axis enumeration, the conjunctive MIN, the threshold theorem (`Λ ≥ 0.90 ⟺ all axes ≥ 0.90`), and the special ≥ 0.95 floor for `moralGrounding`/`measurabilityHonesty` are **none of them formalized in kernel-compiled Lean**.

**Public correction:** [ouroboros-thesis#44](https://github.com/szl-holdings/ouroboros-thesis/pull/44#issuecomment-4467393182)

**Source:** `phd_pods/math_pod_report.md` §"Λ Formalization Verdict"

---

### D5 — `vsp-otel` and `agi-forecast` are README-only (severity: critical for Series A)

**Repo contents (both):** `README.md`, `CITATION.cff`, `LICENSE`, `.github/workflows/scorecard.yml`. **Zero source code.**

**Claim location:** Thesis (PR #44) abstract — "operational Λ measurement via VSP-OTel runtime"
**Reality:** No `LambdaSpanEmitter`, no `ReceiptTracer`, no `RhoClosureEvent`, no OTLP export. No `@opentelemetry/*` SDK dependency anywhere across the org (Dev pod confirmed via lockfile sweep).

PR vsp-otel#4 and agi-forecast#4 ("feat/runtime/...") contain no runtime — they're metadata-only PRs against empty repos.

**Public corrections:**
- [vsp-otel#4](https://github.com/szl-holdings/vsp-otel/pull/4#issuecomment-4467395214)
- [agi-forecast#4](https://github.com/szl-holdings/agi-forecast/pull/4#issuecomment-4467395270)

**Source:** `phd_pods/systems_pod_report.md` §"vsp-otel inventory", `phd_pods/dev_pod_report.md` §"agi-forecast"

---

## High-priority defects

### D6 — `runLoop` kernel has zero integration tests (severity: high)

**Repo:** ouroboros (`src/loop-kernel.ts`)
**Claim:** "218/218 tests passing"
**Reality:** All 218 tests exercise static data tables — frozen constants, policy maps, pure math. The async loop execution path has **never been invoked by a test**. No convergence test, no `AbortSignal` timeout test, no `budgetExhausted` test.

Combined with D5 and the synthetic-Λ test fixtures (D7), the "operational measurement" claim is unsupported by the test suite.

**Public correction:** [ouroboros#31](https://github.com/szl-holdings/ouroboros/pull/31), [ouroboros#32](https://github.com/szl-holdings/ouroboros/pull/32)

**Source:** `phd_pods/dev_pod_report.md` §"Critical Findings — runLoop untested"

---

### D7 — Λ scores in tests are synthetic constants (severity: high)

**Location:** ouroboros loop-kernel test fixtures
**Pattern:** `Array(9).fill(0.7)` — every test feeds the gate fabricated constants instead of deriving scores from runtime artifacts.

**Public correction:** [ouroboros#31, #32 comments](https://github.com/szl-holdings/ouroboros/pull/31#issuecomment-4467395315) (shared with D6)

**Source:** `phd_pods/ml_pod_report.md` §"a11oy agentic core" + `phd_pods/dev_pod_report.md`

---

### D8 — No `AbortSignal` / step timeout in `runLoop` (severity: high)

**Repo:** ouroboros
**Reality:** `runLoop` has no mechanism to bound execution time per step. For an AI runtime calling LLMs, this is a production-blocking API design gap.

**Source:** `phd_pods/dev_pod_report.md` §"Critical Findings"

---

### D9 — GAP-AXIS: two incompatible 9-axis enumerations (severity: medium)

**Locations:**
- `AXES.md` canonical enumeration
- TH2 / arxiv enumeration

**Reality:** These are not the same set. Tracked internally as GAP-AXIS but the thesis abstract presents the 9-axis Λ as a single settled definition. Until resolved, every per-axis claim is ambiguous.

**Source:** `phd_pods/ml_pod_report.md` §"Λ Axis Definition Rigor"

---

### D10 — "Forecast gauge" is a monitoring dashboard, not a forecasting model (severity: medium)

**Repo:** agi-forecast
**Claim:** "Forecast gauge with Brier scoring"
**Reality:** All 12 gauges in the (README-described, not implemented) design are arithmetic ratios of operator-provided scalars. Brier score infrastructure design is described but the ledger is empty; no historical dataset; no held-out test set.

**Source:** `phd_pods/ml_pod_report.md` §"Forecast Gauge"

---

### D11 — `weight_eq` in `IsEgyptianExact` is a tautology (severity: medium)

**Location:** `Lutar/Egyptian.lean`
**Reality:** The constraint `weight_eq` is `1/k = 1/k` — A3 encodes no actual constraint. The associated theorem is vacuous.

**Source:** `phd_pods/math_pod_report.md` §"Top Blocking Issues"

---

### D12 — `TH8b_grade_one_unique` proves `True` via `trivial` while claiming grade-1 uniqueness (severity: medium)

**Location:** PR #18, `TH8/lean_v2/GLR.lean` (or similar)
**Reality:** Theorem statement promises grade-1 uniqueness; proof is `trivial` on `True`. False positive of "proof present."

**Source:** `phd_pods/math_pod_report.md` §"Top Blocking Issues"

---

### D13 — `Term.instantiate` is a stub (severity: medium)

**Location:** lutar-lean (auxiliary file)
**Reality:** `Term.instantiate := fun body _ => body` — beta reduction is semantically broken. Anything depending on this for substitution is unsound.

**Source:** `phd_pods/math_pod_report.md` §"Top Blocking Issues"

---

### D14 — sentra is doc-only in public repo (severity: medium)

**Repo:** sentra
**Reality:** Public repo contains no source. Actual implementation lives in private `szl-holdings/platform` monorepo. CHANGELOG first entry: "Series-A presentation pass." Test badge in README points to ouroboros's test run, misleadingly.

**Source:** `phd_pods/dev_pod_report.md` §"sentra grade D"

---

### D15 — Hardcoded benchmark numbers in agi-forecast README (severity: low-medium)

**Location:** agi-forecast `README.md`
**Reality:** Specific benchmark values dated May 2026 are in the README. With no runtime, no benchmark harness, and no Brier ledger entries, these are aspirational rather than measured.

**Source:** `phd_pods/dev_pod_report.md`

---

### D16 — Runtime contract metadata drift (severity: low)

**File:** `ouroboros-runtime-contract.v2.json`
**Drift:** `"organization": "SZL Consulting LTD"` vs canonical `"SZL Holdings"` in every CITATION.cff across org.

**Source:** `phd_pods/dev_pod_report.md`

---

### D17 — `.github` reusable workflow exempts intra-org refs from SHA-pin (severity: low)

**Repo:** .github
**Reality:** SHA-pin enforcement workflow has an exception for `szl-holdings/*` references — defeats the security model for internal action drift.

**Source:** `phd_pods/dev_pod_report.md` §"`.github` grade A-"

---

### D18 — Scorecard workflow `branch_protection_rule` bug not yet fixed in ouroboros-thesis (severity: low)

**Repo:** ouroboros-thesis
**Reality:** ouroboros fixed this bug; ouroboros-thesis retained the broken version. Easy port.

**Source:** `phd_pods/dev_pod_report.md` §"ouroboros-thesis grade B-"

---

## What is genuinely strong (do not under-sell)

From the pod reports, the following hold up under PhD-tier scrutiny:

- **Loop kernel code quality** (ouroboros `runLoop`) — strong typing, clean supply chain, no forbidden patterns, 218 passing tests for data tables
- **Replayability axis** — fully operationalized, reproducible from DOI-pinned artifacts
- **Doctrine V6 forbidden-pattern compliance** — Dev pod swept all accessible source, zero hits for AlloyScape, Glass Wing, Glasswing, Mythos, "Stephen Paul", "Perplexity Computer", anonymous
- **`.github` reusable workflow library** — A- grade, one minor gap (D17)
- **MeasurabilityHonesty as practice** — 27 documented gaps in GAP_REPORT.md, K13 flagged as unreliable, theorems labelled as conjectures where appropriate (the abstract is the failure point, not the gap practice itself)
- **Mathlib v4.13.0 pinning** — clean version reference, no floating git deps
- **Conjunctive MIN choice over arithmetic mean** — correctly motivated, Theorem 3 (T6 strictness counterexample) is valid
- **CI green across all 16 repos on main** — no broken builds

## Cross-cutting recommendations (operator decision)

1. **Edit arXiv v2 abstract** (PR #44) — replace "sorry-count = 0" with actual count or remove formalization claim from abstract; same for "operational Λ measurement"
2. **Reframe or implement** vsp-otel#4 and agi-forecast#4 — either rename to "scaffold" + update READMEs, or drop real source in this PR
3. **Decide PR #18** — rename to "TH8 scaffolds (uncompiled)" or fold TH8 into lakefile + audit each proof
4. **Add integration tests** for `runLoop` (convergence + abort + budget) before claiming operational
5. **Resolve GAP-AXIS** — one canonical 9-axis enumeration; consistent across paper + code + Lean
6. **Fix `sha256_inj`** — recast as computational hypothesis with explicit security parameter
7. **Implement `Term.instantiate`** properly or remove the dependency
8. **Vacate `weight_eq` tautology** in `IsEgyptianExact` or replace with real constraint

These are the 8 things between "this is a Doctrine V6 compliant Series A package" and where the corpus stands today.

---

## Sweep 2 — 2026-05-16 16:50 EDT (final close-out)

This appendix records the second close-out sweep run after the initial truth-audit. **5 new public actions** taken under CTO authority, **1 defect corrected as false-positive**.

### Actions taken (5)

| # | Defect | Action | Result |
|---|--------|--------|--------|
| 1 | D15 | Patched `agi-forecast/README.md` to rename "Current Value (May 2026)" → "Snapshot Value · As of 2026-05-16" and added an explicit honesty banner | [agi-forecast#9](https://github.com/szl-holdings/agi-forecast/pull/9) — draft, ready for operator review |
| 2 | D16 | Patched `runtime-contract.v3.json` in ouroboros (`"SZL Consulting LTD"` → `"SZL Holdings"`) | [ouroboros#33](https://github.com/szl-holdings/ouroboros/pull/33) — draft |
| 3 | D16 | Patched 3 runtime-contract files in ouroboros-thesis | [ouroboros-thesis#47](https://github.com/szl-holdings/ouroboros-thesis/pull/47) — draft |
| 4 | D2/D3/D11/D12 | Consolidated truth-correction comment on lutar-lean#18 with specific evidence: TH8/ not in lakefile, weight_eq tautology, TH8b_grade_one_unique proves True, sha256_inj is mathematically false | [lutar-lean#18 comment](https://github.com/szl-holdings/lutar-lean/pull/18#issuecomment-4467522329) |
| 5 | D9 (GAP-AXIS) | Posted axis-by-axis diff between `platform/.../lambda.ts` (production) and `ouroboros-thesis/papers/v3/v3-canonical.md` (paper). **5 of 9 axis names differ.** Including a polarity-reversed one (`non_measurability` vs `measurabilityHonesty`) | [ouroboros#31](https://github.com/szl-holdings/ouroboros/pull/31#issuecomment-4467525726) + [ouroboros-thesis#44](https://github.com/szl-holdings/ouroboros-thesis/pull/44#issuecomment-4467525771) |
| 6 | D14 | sentra is doc-only — posted framing-fix asks on sentra#22 and sentra#20 | [sentra#22](https://github.com/szl-holdings/sentra/pull/22#issuecomment-4467521037), [sentra#20](https://github.com/szl-holdings/sentra/pull/20#issuecomment-4467521090) |

### D9 — full per-axis diff (final canonical record)

| # | Runtime (lambda.ts) | Thesis (v3-canonical.md) | Match |
|---|---------------------|--------------------------|:----:|
| 1 | cleanliness | cleanliness | ✅ |
| 2 | horizon | horizon | ✅ |
| 3 | resonance | resonance | ✅ |
| 4 | frustum | frustum | ✅ |
| 5 | gaussClosure | geometry | ❌ |
| 6 | invariance | invariance | ✅ |
| 7 | moralGrounding | moral | ❌ |
| 8 | ontologicalGrounding | being | ❌ |
| 9 | measurabilityHonesty | non_measurability | ❌ (polarity reversed) |

### D17 CORRECTION — downgraded to non-defect

Original framing: ".github SHA-pin policy exempts `szl-holdings/*` (supply-chain regression)."

After re-reading `.github/workflows/pin-check.yml` in context:
- `pin-check.yml` is a **self-check** that runs only on `.github`'s own workflow files.
- Consumer repos like `ouroboros` already SHA-pin their references to `szl-holdings/.github` reusable workflows — the full 40-char SHAs are present in their `ci.yml`.
- The `szl-holdings/*` exemption applies inside the central `.github` repo's self-check only, where reusable workflows internally reference each other. It does not propagate.

**Verdict:** D17 was a false-positive. Downgraded to non-defect. Recorded publicly at [.github#37 comment](https://github.com/szl-holdings/.github/pull/37#issuecomment-4467527160).

Doctrine V6 measurabilityHonesty includes the honesty of correcting our own previous audit when re-verification disproves it. Recording this here is part of the audit, not separate from it.

### Updated defect count

- Original: 18 defects (D1–D18)
- After D17 correction: **17 active defects**
- Of those: D15 + D16 have draft PRs in flight (4 file changes). Remaining 15 are either Lean-source defects requiring proof work, scope/framing decisions (operator), or implementation gaps (operator/team).

### Operator-only outstanding (unchanged)

1. Mint 12 Zenodo DOIs
2. Submit arXiv v2 (after editing abstract per D1)
3. License allowlist decision on 7 LicenseRef-SZL-Proprietary repos
4. Branch protection on lutar-lean, vsp-otel, agi-forecast
5. DOI rebind for szl-trust#11 (concept → versioned)
6. OpenSSF Best Practices badge registration
7. 2nd reviewer to unblock merges
8. PR #18 framing decision (scaffold rename vs lakefile fold)
9. Implement vsp-otel + agi-forecast or reframe PRs as scaffold
10. Force-push resolution on PR #34 (14 conflict regions across `papers/v{5,6,7,8,12}/`)

### Sweep 2 closing note

Author: Stephen P. Lutar Jr. — `stephen@szlholdings.com` — ORCID `0009-0001-0110-4173` — SZL Holdings
Authority: CTO. All draft PRs above need operator ready-for-review flip and 2nd reviewer to merge.
Doctrine: V6 — moralGrounding + measurabilityHonesty ≥ 0.95. No bandaids, no hallucinations.
