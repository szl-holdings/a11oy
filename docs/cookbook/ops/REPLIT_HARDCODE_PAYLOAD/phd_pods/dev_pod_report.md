# PhD Dev Pod — SZL Holdings Engineering Audit Report

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

<!-- ARCHIVED-THESIS-NOTICE -->
> **⚠️ Archived thesis notice.** The `szl-holdings/ouroboros-thesis` repository has been retired; the Ouroboros Thesis is now archived at Zenodo DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276). Any `ouroboros-thesis` references below are **historical and not live**.

**Doctrine:** V6 — strict, evidence-only, no hallucinations  
**Auditor class:** PhD-level Software Engineering reviewer  
**Scope:** szl-holdings org — repos: `ouroboros`, `ouroboros-thesis`, `sentra`, `vsp-otel`, `agi-forecast`, `.github`  
**Evidence source:** GitHub API read-only (`gh api /repos/szl-holdings/{repo}/...`)  
**Date of audit:** 2026-07-09  

---

## Executive Scorecard

| Repo | Tests | CI Complete | Lockfile | Type Safety | API Surface | Observability | Error Handling | Doctrine | Reviewer Grade |
|---|---|---|---|---|---|---|---|---|---|
| **ouroboros** | ⚠️ Partial | ⚠️ Missing SBOM, no format gate | ✅ pnpm-lock.yaml w/ SHA | ✅ TS strict | ✅ Full exports + README | ❌ Zero OTel hooks | ⚠️ No kernel test; propagate-by-design | ✅ Clean | C+ |
| **ouroboros-thesis** | ❌ Zero (paper repo) | ⚠️ Docs-CI only; scorecard bug | N/A (no build) | N/A (no code) | ⚠️ Implicit (contracts as JSON) | ❌ N/A | N/A | ✅ Clean | B- |
| **sentra** | ❌ Zero | ⚠️ Docs-CI only; no CodeQL on JS | N/A (no source) | N/A (no code) | ❌ No public API | ❌ N/A | N/A | ✅ Clean | D |
| **vsp-otel** | ❌ Zero | ❌ Scorecard only | ❌ No lockfile | N/A (no code) | ❌ Pre-impl proposal only | ❌ Zero (pre-impl) | N/A | ✅ Clean | F |
| **agi-forecast** | ❌ Zero | ❌ Scorecard only | ❌ No lockfile | N/A (no code) | ❌ Pre-impl proposal only | N/A | N/A | ✅ Clean | F |
| **.github** | N/A | ✅ Pin-check enforced | N/A | N/A | ✅ Reusable workflow library | N/A | ✅ pin-check shell robust | ✅ Clean | A- |

**Grade key:** A = production-ready; B = minor gaps; C = significant gaps; D = skeleton only; F = stub/proposal.

---

## Axis-by-Axis Evidence

### Axis 1 — Test Coverage

#### `ouroboros`

Test infrastructure: `vitest.config.ts` exists; `pnpm test` script defined in `package.json`.  
Source: `gh api /repos/szl-holdings/ouroboros/contents/vitest.config.ts` — includes `['src/**/*.test.ts', 'packages/**/src/**/*.test.ts']`.

**Test files found** (via `gh api /repos/szl-holdings/ouroboros/git/trees/HEAD?recursive=1`):
- `src/runtime-contract.test.ts` — tests proof-route resolver, risk-tier gate, almanac advancer, immutability guards
- `packages/ouroboros/src/runtime-contract.test.ts` — same pattern, v3+ surface
- `packages/ouroboros/src/runtime-contract.v4.test.ts` — v4 validator registry, ingestion contracts, routing tables
- `packages/ouroboros/src/v4-validators/v4-validators.test.ts` — 9 validator functions, pass/fail per function
- `packages/ouroboros/src/lutar-invariant-proof.test.ts` — axiom A1–A4 numerical witnesses (22 tests)
- `packages/ouroboros/src/v6-payload.test.ts` — v6 services, halt conditions, routing, permissions
- `packages/ouroboros/src/gov-readiness.test.ts` — platform readiness score pinning

**Critical gap — `runLoop` kernel is NEVER tested directly.**  
All 7 test files exercise static data tables, pure math functions, and frozen contracts. The `runLoop` async execution path (`src/loop-kernel.ts`, `packages/ouroboros/src/loop-kernel.ts`) has **zero test invocations** across all test files. Confirmed by grepping every test file for `"runLoop"` and `"LoopTrace"` — zero matches.

Evidence: `gh api /repos/szl-holdings/ouroboros/contents/src/runtime-contract.test.ts` — the one file named most similarly to a kernel integration test contains only `resolveProofRoute`, `evaluateRiskTier`, `advanceAlmanac`, `rebuildAlmanac` calls.

**Coverage configuration:** `vitest.config.ts` has no `coverage` section. No `--coverage` flag. No coverage thresholds enforced anywhere. The README badge claims "218/218" but no CI step measures line/branch coverage, so the 218 count is a test-count not a coverage percentage.

**Missing tests for:**  
- `runLoop()` with step functions (convergence, abort, budget-exhausted paths)  
- `allocateDepth()` function  
- `numericConsistency`, `vectorConsistency`, `stringConsistency`, `setConsistency` helpers  
- React components (`LoopGlyph.tsx`, `OuroborosTrace.tsx`) — no render tests  
- Edge cases: `delta` throws, `step` throws, `maxSteps=0`

#### `ouroboros-thesis`

No source code. Repo contains LaTeX/Markdown papers, JSON contracts, figures, and BibTeX.  
**No test infrastructure, none expected.** Paper repo.

#### `sentra`

No source code. Repo is a showcase/metadata repository.  
Source: `gh api /repos/szl-holdings/sentra/git/trees/HEAD?recursive=1` — files are `.github/**`, `CHANGELOG.md`, `CITATION.cff`, governance docs, `social-preview.svg`. Zero `.ts`, `.py`, or `.go` files.  
**ZERO tests. No test infrastructure.**

#### `vsp-otel`

No source code. Pre-implementation proposal.  
Source: `gh api /repos/szl-holdings/vsp-otel/git/trees/HEAD?recursive=1` — only `.github/workflows/scorecard.yml`, `CITATION.cff`, `LICENSE`, `README.md`.  
**ZERO tests. Pre-implementation.**

#### `agi-forecast`

No source code. Pre-implementation stub.  
Source: `gh api /repos/szl-holdings/agi-forecast/git/trees/HEAD?recursive=1` — same 4 files.  
**ZERO tests. Pre-implementation.**

#### `.github`

Template/reusable workflow repo. No application code. Test coverage N/A.

---

### Axis 2 — CI Completeness

**Reusable workflow library** (`szl-holdings/.github`):  
Source: `gh api /repos/szl-holdings/.github/contents/.github/workflows`

Available reusables: `reusable-node-ci.yml`, `reusable-codeql.yml`, `reusable-dependency-review.yml`, `reusable-docs-ci.yml`, `reusable-gitleaks.yml`, `reusable-release-please.yml`, `reusable-sbom.yml`, `reusable-scorecard.yml`, `reusable-secret-scan.yml`, `reusable-trivy.yml`, `reusable-workflow-lint.yml`, `pin-check.yml`.

All external actions are SHA-pinned (enforced by `pin-check.yml`). Runner hardening via `step-security/harden-runner` on every job.

#### `ouroboros`

CI file: `gh api /repos/szl-holdings/ouroboros/contents/.github/workflows/ci.yml`

Jobs wired:
- ✅ `ci` → `reusable-node-ci.yml` (lint, typecheck, test, build)
- ✅ `codeql` → `reusable-codeql.yml` (languages: `["javascript-typescript"]`)
- ✅ `secrets` → `reusable-secret-scan.yml` (TruffleHog)
- ✅ `dependency-review` → `reusable-dependency-review.yml` (PR only)
- ✅ `trivy` → `reusable-trivy.yml`
- ✅ `scorecard` → separate `scorecard.yml`

**Missing:**
- ❌ **SBOM** — `reusable-sbom.yml` exists in the org but is NOT called. A production library that claims audit-grade governance should generate a CycloneDX + SPDX SBOM on release.
- ❌ **Format gate** — `biome format` is available in `package.json` scripts but not invoked by CI. The `reusable-node-ci.yml` runs the `test`, `lint`, `typecheck`, `build` matrix tasks, and `lint:ci` is defined but `format:ci` is absent. Formatting violations can silently land on main.
- ❌ **Gitleaks** — `reusable-gitleaks.yml` exists but is not called. Secret scan uses TruffleHog only.
- ❌ **Release pipeline** — `reusable-release-please.yml` exists but is not wired. No automated release workflow. Releases appear to be manual.

#### `ouroboros-thesis`

Jobs wired (source: `gh api /repos/szl-holdings/ouroboros-thesis/contents/.github/workflows/ci.yml`):
- ✅ `docs` → `reusable-docs-ci.yml`
- ✅ `secrets` → `reusable-secret-scan.yml`
- ✅ `scorecard` → `scorecard.yml`
- ✅ `docs-only-paths-guard` → custom path-enforcement workflow

**Bug:** `ouroboros-thesis/scorecard.yml` retains the `branch_protection_rule` trigger that `ouroboros/scorecard.yml` explicitly removed (with comment explaining the `startup_failure` risk). Also uses `permissions: read-all` instead of `permissions: {}` at the top level, which is the pattern ouroboros fixed.

Evidence — ouroboros scorecard.yml comment:
> "Removed `branch_protection_rule` trigger — that event runs without commit context and causes startup_failure."

The thesis scorecard has not received this fix.

#### `sentra`

Jobs (source: `gh api /repos/szl-holdings/sentra/contents/.github/workflows/ci.yml`):
- ✅ `docs` → `reusable-docs-ci.yml`
- ✅ `secrets` → `reusable-secret-scan.yml`
- ✅ `codeql` → `codeql.yml` (languages: `[actions]` only)
- ✅ `scorecard`

Sentra's `codeql.yml` scans `actions` language only. If/when TypeScript source is added, the `codeql.yml` will not cover it without amendment.

#### `vsp-otel`

Only `scorecard.yml`.  
**Missing:** CI build, lint, test, CodeQL, secret scan, dependency review, SBOM. All absent.

#### `agi-forecast`

Only `scorecard.yml`.  
**Missing:** Same as vsp-otel.

#### `.github`

- ✅ `pin-check.yml` — SHA-pin enforcement on every workflow push/PR  
- ✅ `scorecard.yml`  
- All reusable workflows have harden-runner and SHA-pinned actions.

**Gap:** No `reusable-workflow-lint.yml` self-call in CI to validate its own YAML. Potential for malformed workflow files to land undetected.

---

### Axis 3 — Build Reproducibility

#### `ouroboros`

- ✅ `pnpm-lock.yaml` present at root (lockfileVersion `9.0`, source: `gh api /repos/szl-holdings/ouroboros/contents/pnpm-lock.yaml`)
- ✅ All packages have `resolution: {integrity: sha512-...}` hashes. SHA-512 content hashes present for all dependencies. Confirmed by reading integrity lines.
- ✅ `.npmrc` and `.node-version` / `.nvmrc` present, pinning Node version.
- ✅ `packageManager: "pnpm@10.26.1"` declared in `package.json` — corepack-compatible.
- ✅ CI uses `--frozen-lockfile` when lockfile detected (see `reusable-node-ci.yml` install step).

**Gap:** Package uses semver ranges (`^2.4.14`, `^25.6.0`, etc.) in `devDependencies`. While the lockfile pins exact versions at install time, the ranges permit future drift if the lockfile is regenerated. Production-grade supply chain practice would use exact versions in `package.json` or ship a verified lockfile as the truth source. This is acceptable for a dev dependency-only package (no runtime deps) but worth noting.

**Note:** `package.json` declares `"dependencies": {}` — zero runtime dependencies. All deps are `devDependencies`. This is clean for a library that compiles to pure TS/ESM.

#### `sentra`, `vsp-otel`, `agi-forecast`

No package manifest of any kind. No lockfile. **Not applicable** (no build artifact).

#### `ouroboros-thesis`

No build toolchain. Python script `figures/build_all.py` for figure generation but no `requirements.txt` or `pyproject.toml`. **Reproducibility risk for figure generation.**

#### `.github`

Bash scripts only. No build system.

---

### Axis 4 — Type Safety

#### `ouroboros`

Source: `gh api /repos/szl-holdings/ouroboros/contents/tsconfig.json`

```json
{
  "compilerOptions": {
    "strict": true,
    ...
    "verbatimModuleSyntax": true
  }
}
```

- ✅ `"strict": true` — enables `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, etc.
- ✅ `"verbatimModuleSyntax": true` — prevents type-only imports from polluting runtime output.
- ✅ No `ts-ignore` or `as any` found in any read source file.

**Gap:**  
- `"skipLibCheck": true` is set. This suppresses type errors in `.d.ts` files. It prevents catching issues from dependency type conflicts but is standard practice for library development to avoid upstream definition noise.
- No `noUncheckedIndexedAccess: true`. Array subscript access `a[i]` returns `T` not `T | undefined`. Visible in `consistency.ts` line `const ai = a[i] ?? 0` which compensates, but TypeScript itself won't warn on `a[i]` uses that skip the guard.
- No `exactOptionalPropertyTypes: true`. Optional properties (`?: T`) allow `undefined` assignment, which can mask intent.

The TypeScript compiler is configured correctly for the project's production bar. The gaps above are elite-level practices not commonly enforced.

#### `sentra`, `vsp-otel`, `agi-forecast`

No TypeScript source. N/A.

#### `ouroboros-thesis`

No code. N/A.

#### Lean 4 (referenced but out-of-scope)

The audit notes that `szl-holdings/lutar-lean` (referenced from README but not in the audited repo list) uses Lean 4. Lean's type system is constructive and type-safe by construction; every theorem is checked at elaboration time.

---

### Axis 5 — Public API Discoverability

#### `ouroboros`

Source: `src/index.ts`, `README.md` Modules section.

✅ **Explicit exports** via `src/index.ts` and `packages/ouroboros/src/index.ts`:
All exported symbols are listed explicitly with `export type` and `export` declarations. `package.json` maps each subpath (`.`, `./types`, `./loop-kernel`, `./consistency`, `./depth-allocator`, `./react`) to distinct `types:` and `import:` fields.

✅ **README API section** exists: a full Modules table lists every export with one-line purpose, cross-linked to the paper section where the algorithm is formalized.

**Gaps:**  
- No auto-generated API docs (TypeDoc, tsdoc). The exported types are well-commented but have no rendered HTML docs or Storybook.
- The `./react` export is not documented in the Modules table (only `LoopGlyph.tsx` and `OuroborosTrace.tsx` components, with no prop-level docs visible).
- The `packages/ouroboros/src/index.ts` exports a larger surface (v4, v6, gov-readiness symbols) than `src/index.ts` but the README's Modules section partially describes v6. The relationship between the root `src/` tree and the `packages/ouroboros/src/` tree is not explained — a new contributor would not know which `index.ts` is the canonical entry point.

#### `sentra`

README exists and describes the domain surface. However:  
- No exported TypeScript types or functions (no source code).  
- The "pipeline" (`sense → structure → correlate → explain → recommend → approve → execute → proof`) is described in prose only.  
- ❌ No public API — described as "Alpha; under active development."

#### `vsp-otel`, `agi-forecast`

Pre-implementation. README describes intended design. No exported surface.

---

### Axis 6 — Observability

#### `ouroboros`

The `src/` and `packages/ouroboros/src/` trees contain no OpenTelemetry instrumentation.  
- No `@opentelemetry/*` dependencies in `package.json`.  
- No span creation, trace context propagation, or metric emission.  
- The `LoopTrace` type provides a structural trace of a loop run (steps, durations, exit reasons) that is **human-readable and inspectable** but is not emitted to any OTel backend.  
- No `console.error` / structured logging hooks either.

**The entire observability story is deferred to `vsp-otel`.** The README acknowledges this: the `trace_runtime` and `receipt_runtime` services are declared in `SHARED_RUNTIME_SERVICES_V6` (source: `v6-payload.ts`) but are conceptual entries in a frozen array — there is no runtime code that actually calls an OTel SDK.

Evidence — `vsp-otel` README:
> "This closes the P1 gap ('Zero OTel GenAI SemConv coverage; no per-span cost or token-usage telemetry')"

This gap is confirmed: as of the current main branch, there is literally zero OTel instrumentation anywhere in the audited codebase.

**Positive:** `LoopTrace.totalDurationMs` and per-step `durationMs` fields provide timing data that a caller could use to build their own telemetry. The `LoopTrace.id` and `label` fields enable correlation.

#### `vsp-otel`

Pre-implementation. The README is an executive summary and architecture proposal. No code exists.  
Source: `gh api /repos/szl-holdings/vsp-otel/git/trees/HEAD?recursive=1` — 4 files total.

#### All other repos

No observability surface. Not applicable.

---

### Axis 7 — Error Handling

Three source files sampled per repo with source code.

#### `ouroboros` — Sample 1: `src/loop-kernel.ts`

**Pattern:** Explicit "never swallows" doctrine stated in comment:
```
// Kernel never swallows errors — let any throw from step propagate to the caller.
const result: StepResult<S, O> = await step(state, i);
```
(Source: `gh api /repos/szl-holdings/ouroboros/contents/src/loop-kernel.ts`, line ~84)

No try/catch. This is an **intentional propagation design** — the kernel is a library primitive, not an application. The caller is responsible for wrapping. This is legitimate but means any exception in `step()` or `delta()` will propagate unhandled through `runLoop()` and crash the caller. There is no timeout protection for runaway async steps.

**Gap:** No `AbortSignal` or timeout parameter on `runLoop`. A step that hangs indefinitely will cause `runLoop` to hang indefinitely. For a production AI runtime kernel, this is a material omission.

#### `ouroboros` — Sample 2: `src/consistency.ts`

**Pattern:** Defensive undefined checks:
```typescript
if (a === undefined || b === undefined) return 0;
if (!Number.isFinite(a) || !Number.isFinite(b)) return 0;
```
Guards `NaN`, `Infinity`, and `undefined` inputs consistently. `stringConsistency` adds a fast path for pathological inputs:
```typescript
if (m * n > 200_000) {
  // Fast path for very long strings: token-overlap Jaccard.
```
Error handling is **strong** in this module.

#### `ouroboros` — Sample 3: `packages/ouroboros/src/v4-validators/validators.ts`

**Pattern:** Every validator is a pure function with typed input. No exceptions thrown; results are typed `ValidatorResult`:
```typescript
function pass(id: string, note?: string): ValidatorResult { ... }
function fail(id: string, note: string): ValidatorResult { ... }
```
Frozen result objects. No implicit state mutation. Error paths return `fail()` objects rather than throwing.

This is **excellent** — the Result pattern is used throughout. The one gap is that the validator functions receive a `RuntimeContext` that uses optional fields (`ctx.tokensUsed !== undefined`) but there is no schema validator on `RuntimeContext` itself — a caller passing a malformed object gets vacuous `pass()` results (e.g., `valBudgetEnforcer({})` returns `pass`).

#### `ouroboros` — Sample 4: `src/depth-allocator.ts`

`allocateDepth` filters `NaN`/non-finite deltas:
```typescript
const deltas = input.recentDeltas.filter((d) => Number.isFinite(d));
```
Returns a safe default when no valid deltas:
```typescript
if (deltas.length === 0) { return { ..., trajectory: 'unknown', ... }; }
```
**Strong defensive handling.**

#### `sentra`, `vsp-otel`, `agi-forecast`

No source code to sample.

---

### Axis 8 — Doctrine Compliance

Searched all accessible source files for: `AlloyScape`, `Glass Wing`, `Glasswing`, `Mythos`, `Stephen Paul`, `Perplexity Computer`, `anonymous`.

**Repos searched:** `ouroboros` (all `src/**/*.ts`, README, LUTAR_EVIDENCE, CITATION.cff, CHANGELOG), `ouroboros-thesis` (thesis.md, README, CITATION.cff), `sentra` (README, CITATION.cff), `vsp-otel` (README), `agi-forecast` (README), `.github` (all workflows, README, WORKFLOWS.md, SUPPORT.md).

**Result: ZERO hits on any forbidden pattern.**

The name `Stephen P. Lutar` (or `Stephen P. Lutar Jr.`) appears in CITATION.cff files and README footers as the stated author. This is the legal/academic name attribution, not a doctrine violation. The forbidden term `Stephen Paul` (as a search string) does not appear anywhere.

---

### Axis 9 — Reviewer-Grade Defects Per Repo

#### `ouroboros` — Top 3 PhD-tier blocks

**Block 1: `runLoop` kernel has zero integration tests.**  
The primary exported primitive — the loop kernel implementing the core thesis claim — has never been executed in a test harness. A convergence test, an abort test, and a `budgetExhausted` test would each require < 10 lines of code and would have caught multiple categories of regressions. Every claim in the README ("218/218 passing") is accurate for the static data-table tests but misleading about kernel correctness. A reviewer would require at minimum:
- `runLoop` converges in < N steps on a contracting map
- `runLoop` respects `maxSteps` exactly
- `runLoop` aborts when `step` returns `{ abort: true }`
- `runLoop` propagates exceptions from `step` to caller (to document the no-catch contract)
- `allocateDepth` + `consistency` helpers tested with property-based inputs

**Block 2: No `AbortSignal` / step timeout in `runLoop`.**  
For an AI runtime kernel where step functions call LLMs or external services, an unbounded `await step(state, i)` is a production-blocking omission. The current API has no timeout parameter, no cancellation token, and no deadline mechanism. Any consumer running `runLoop` with a network-calling step has no way to bound execution time. This is a fundamental API design gap for an async runtime primitive.

**Block 3: No code coverage enforcement.**  
`vitest.config.ts` has no `coverage` section. The CI matrix runs `vitest run` but does not emit coverage. With a library claiming "218/218" test coverage, the absence of branch/line coverage thresholds means the 218 count is a **head count of test cases, not a coverage metric**. Large execution paths (all loop kernel branches, all consistency edge cases, React render paths) are uncovered and would silently regress.

---

#### `ouroboros-thesis` — Top 3 PhD-tier blocks

**Block 1: Scorecard workflow retains `branch_protection_rule` trigger and `permissions: read-all`.**  
Source: `gh api /repos/szl-holdings/ouroboros-thesis/contents/.github/workflows/scorecard.yml` — contains `branch_protection_rule:` trigger. The sibling repo (`ouroboros`) explicitly removed this trigger with a documented reason: "that event runs without commit context and causes startup_failure." The thesis repo has not received this fix, meaning its Scorecard runs likely produce `startup_failure` on branch protection changes. `permissions: read-all` at workflow level is the broad grant pattern that `ouroboros` also fixed.

**Block 2: `figures/build_all.py` has no declared Python dependency manifest.**  
The figure generation script exists at `gh api /repos/szl-holdings/ouroboros-thesis/contents/figures/build_all.py` but there is no `requirements.txt`, `pyproject.toml`, or `setup.py`. Reproducing the figures requires guessing which matplotlib/numpy version was used. For a paper claiming machine-verifiable reproducibility, figure generation reproducibility is a scholarly obligation.

**Block 3: The `ouroboros-runtime-contract.v2.json` author field differs from canonical author attribution.**  
Source: `gh api /repos/szl-holdings/ouroboros-thesis/contents/ouroboros-runtime-contract.v2.json` — `"author": "Stephen P. Lutar Jr."` (with Jr. suffix) while all CITATION.cff files use `"given-names": "Stephen P."` without suffix. This metadata inconsistency between the primary contract artifact and the canonical academic citations creates citation ambiguity. The `"organization": "SZL Consulting LTD"` also differs from the org name `SZL Holdings` used everywhere else.

---

#### `sentra` — Top 3 PhD-tier blocks

**Block 1: Badge claims are unverifiable because no source code exists.**  
README badge: `[![Runtime tests](https://img.shields.io/badge/runtime%20tests-218%2F218-2DA44E...)](https://github.com/szl-holdings/ouroboros)` — this badge points to the `ouroboros` repo, not sentra. Sentra itself has zero tests. A reader of the sentra README would reasonably believe sentra's code is tested 218/218. This is misleading badge attribution.

**Block 2: No source code, no exported API, yet described as "cyber resilience command" platform with active CI.**  
CI runs docs-CI and CodeQL (for `actions` language only). The `codeql.yml` scans GitHub Actions YAML — correct — but a CodeQL badge on a repo with no application code creates false confidence for a security reviewer. The repo is a placeholder, not a product component.

**Block 3: `CHANGELOG.md` describes a "Series-A presentation pass" as the primary development milestone.**  
Source: `gh api /repos/szl-holdings/sentra/contents/CHANGELOG.md`:
```
### Added
- Series-A presentation pass: SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CODEOWNERS
```
The first entry in the changelog is investor-facing governance document creation, not functional feature delivery. There is no implementation code; the project exists as governance scaffolding rather than software. This inverts the expected development sequence (build → document → govern).

---

#### `vsp-otel` — Top 3 PhD-tier blocks

**Block 1: Entire repository is a proposal document, not software.**  
Source: `gh api /repos/szl-holdings/vsp-otel/git/trees/HEAD?recursive=1` — 4 files: `scorecard.yml`, `CITATION.cff`, `LICENSE`, `README.md`. Zero source files. A CITATION.cff exists for an unimplemented library. Publishing academic citations for pre-implementation proposals misrepresents the artifact's readiness state.

**Block 2: README claims quantitative implementation promises without any code.**  
README: "No regression on p50 11.5 µs. Receipt size stays ≤ 256 bytes. Shippable in 4 weeks." These are future-state promises in a README presented as specification, not implementation notes. A citable repository with a `CITATION.cff` that makes performance claims is academically problematic if no benchmark or test exists to verify them.

**Block 3: Scorecard only CI on a proposed library.**  
Only `scorecard.yml` is present. The OSSF Scorecard will produce a low score for a repo with no branch protection test, no CI, no tests, no dependency pinning — but the score is meaningless here because there is no software to protect. Investing in scorecard before implementation is CI theater.

---

#### `agi-forecast` — Top 3 PhD-tier blocks

**Block 1: Static data tables hardcoded in README as of May 2026, no automated ingestion pipeline.**  
The 12 AGI gauge variables (METR-th50-hours, Epoch-frontier-flops, etc.) are hardcoded in the README with a "Current Value (May 2026)" annotation. The repo's declared purpose is to produce "receipt-attested forecast gauges" but there is no ETL pipeline, no data fetching code, and no automated update mechanism. The data is already stale by design.

**Block 2: DOI-pinned citation for data that will change.**  
`CITATION.cff` assigns a citable reference to a repo whose core content is time-sensitive benchmark values that have no update mechanism. Citing the repo in a paper would freeze a specific data snapshot, but the repo's own README presents values as "current" without any versioning strategy for the data itself.

**Block 3: Same as vsp-otel Block 3 — Scorecard only CI on a stub.**  
Evidence: `gh api /repos/szl-holdings/agi-forecast/git/trees/HEAD?recursive=1` — identical 4-file structure to vsp-otel.

---

#### `.github` — Top 3 PhD-tier blocks

**Block 1: `pin-check.yml` allows `szl-holdings/*` refs without SHA verification.**  
Source: `gh api /repos/szl-holdings/.github/contents/.github/workflows/pin-check.yml`:
```bash
# Reusable workflows live in this org and may use @main — allow that
[[ "$ref" == szl-holdings/* ]] && continue
```
All callers in the org use SHA-pinned refs (e.g., `@c8359e53b40560f15ed5c25c3e4e1256b0536cf8`) which is correct. However, the pin-check exempts *any* `szl-holdings/*` ref, meaning a `uses: szl-holdings/some-repo/.github/workflows/evil.yml@main` in a workflow would pass the check. If a repo inside the org is compromised, this exemption becomes a lateral movement vector. The check should verify that intra-org refs are also SHA-pinned.

**Block 2: `reusable-node-ci.yml` silently skips tasks when no script is defined.**  
Source: `gh api /repos/szl-holdings/.github/contents/.github/workflows/reusable-node-ci.yml`:
```bash
# Skip silently if the script isn't defined
if ! node -e "const p=require('./package.json'); ..."; then
  echo "::notice::No '${{ matrix.task }}' script in package.json — skipping"
  exit 0
fi
```
A typo in `package.json` (`"tes"` instead of `"test"`) would silently pass CI instead of failing. The skip-and-pass behavior means callers cannot distinguish "CI ran tests" from "CI skipped tests because the script was missing." This creates invisible coverage gaps.

**Block 3: `reusable-docs-ci.yml` uses `markdownlint-cli2-action` with `continue-on-error: true`.**  
Source: `reusable-docs-ci.yml`, `markdown-lint` job:
```yaml
continue-on-error: true
```
Markdown lint violations do not fail the build. This means the lint job is informational only. For a governance document repository, silent lint failures undermine the value of the check.

---

## Top 10 Cross-Cutting Recommendations (Priority Order)

### P1 — Write integration tests for `runLoop`

**Severity:** Critical. Blocking for any production claim.  
The loop kernel (`src/loop-kernel.ts`, `packages/ouroboros/src/loop-kernel.ts`) is the thesis-central execution primitive. It has zero test coverage. A convergence test (3 lines), abort test (5 lines), budget-exhaustion test (3 lines), and exception-propagation test (5 lines) would provide a meaningful regression baseline. Add these to `src/loop-kernel.test.ts`.

Recommended minimum:
```typescript
it('converges when delta drops to zero', async () => { ... runLoop with contracting map ... });
it('respects maxSteps exactly', async () => { ... count steps in budgetExhausted trace ... });
it('aborts when step returns { abort: true }', async () => { ... });
it('propagates exceptions from step to caller', async () => { ... });
```

### P2 — Add `AbortSignal` or `stepTimeoutMs` to `runLoop`

**Severity:** Critical for production use.  
The current API has no mechanism to bound execution time per step. Any consumer using async steps (LLM calls, network IO) has no way to prevent hangs. Add a `config.stepTimeoutMs?: number` parameter that wraps each `await step(state, i)` in a `Promise.race` with a rejection timeout.

### P3 — Enforce coverage thresholds in CI

**Severity:** High.  
Add a `coverage` section to `vitest.config.ts`:
```typescript
coverage: {
  provider: 'v8',
  thresholds: { lines: 85, branches: 80, functions: 90, statements: 85 },
  include: ['src/**/*.ts', 'packages/ouroboros/src/**/*.ts'],
  exclude: ['**/*.test.ts', 'src/react/**']
}
```
Wire `pnpm run test:coverage` in the CI matrix. Without this, the "218/218" count is meaningless as a quality signal.

### P4 — Add SBOM generation to `ouroboros` CI

**Severity:** High. Required for enterprise/government procurement.  
`reusable-sbom.yml` exists in the org but is not called by any repo. Add an `sbom` job to `ouroboros/ci.yml`:
```yaml
sbom:
  uses: szl-holdings/.github/.github/workflows/reusable-sbom.yml@{SHA}
```
The README explicitly targets government procurement; SBOM is a stated checklist item.

### P5 — Add format enforcement to `ouroboros` CI

**Severity:** Medium.  
`biome format --write` is available but not run in CI. Add `"format:ci": "biome format --check ./src"` to `package.json` and wire it through `reusable-node-ci.yml` or as a separate job. Formatting violations currently pass CI silently.

### P6 — Fix `ouroboros-thesis` Scorecard workflow

**Severity:** Medium.  
Remove `branch_protection_rule:` trigger and replace `permissions: read-all` with `permissions: {}` + job-level scopes, matching the pattern already applied in `ouroboros/scorecard.yml`. The ouroboros repo explicitly documented why this was necessary; the thesis repo is lagging this fix.

### P7 — Document the dual-tree architecture (`src/` vs `packages/ouroboros/src/`)

**Severity:** Medium.  
The ouroboros repo has two parallel source trees: `src/` (v1–v2 contract modules) and `packages/ouroboros/src/` (v3–v6 modules, the primary package for the platform). A new contributor reading `README.md` encounters the v6 module table but cannot tell which `index.ts` is canonical. Add a `ARCHITECTURE.md` or a root-level `README.md` section that states: "`packages/ouroboros/` is the main publishable package; `src/` is the v1–v2 contract reference implementation."

### P8 — Add `noUncheckedIndexedAccess` to `tsconfig.json`

**Severity:** Low–Medium.  
Several `consistency.ts` and `depth-allocator.ts` functions access `a[i]` with `?? 0` guards (defensive), but TypeScript does not require this because `noUncheckedIndexedAccess` is off. Enabling this flag would make the existing guards type-required rather than voluntary, preventing any future contributor from omitting them. This is one of the few `strict`-extension flags that catches real bugs in array-heavy code.

### P9 — Remove misleading runtime-test badges from `sentra` README

**Severity:** Medium.  
The badges `[![Runtime tests](... 218/218 ...)](https://github.com/szl-holdings/ouroboros)` and `[![runtime DOI](... ouroboros DOI ...)]` in `sentra/README.md` attribute ouroboros test results to sentra. Replace these with `[![Tests](... not yet implemented ...)]` or remove them until sentra ships source code with its own test suite.

### P10 — Implement `vsp-otel` or demote to `docs/` or issue

**Severity:** Low (strategic).  
A repository consisting of 4 files — a `scorecard.yml`, `CITATION.cff`, `LICENSE`, and a proposal README — with a CITATION.cff providing DOI-ready metadata creates scholarly record for an unimplemented library. Either:
a. Implement the library (VSP is described as a 4-week project), or  
b. Move the proposal to `ouroboros/docs/vsp-proposal.md` and close the standalone repo, or  
c. Clearly mark the CITATION.cff status as `proposal` and add `status: pre-implementation` to the README front matter.

The same applies to `agi-forecast`.

---

## Direct Source Quotes

**ouroboros `src/loop-kernel.ts`** — documented no-catch policy:
> `"// Kernel never swallows errors — let any throw from step propagate to the caller."`

**ouroboros `scorecard.yml`** — explains trigger removal fix:
> `"Removed \`branch_protection_rule\` trigger — that event runs without commit context and causes startup_failure."`

**ouroboros `reusable-node-ci.yml`** — silent skip on missing script:
> `"# Skip silently if the script isn't defined"` → `"exit 0"`

**`reusable-docs-ci.yml`** — non-blocking lint:
> `"continue-on-error: true"` on `markdownlint-cli2-action`

**`vsp-otel/README.md`** — acknowledges the observability gap this repo is meant to close:
> `"This closes the P1 gap ('Zero OTel GenAI SemConv coverage; no per-span cost or token-usage telemetry')"`

**`agi-forecast/README.md`** — hardcoded benchmark values:
> `"| 1 | \`METR-th50-hours\` | [metr.org/time-horizons](https://metr.org/time-horizons/) | ≥16 h (ceiling) |"` — with `"Current Value (May 2026)"` column header.

**`sentra/CHANGELOG.md`** — first milestone entry:
> `"### Added\n- Series-A presentation pass: SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CODEOWNERS"`

**`ouroboros-runtime-contract.v2.json`** — author metadata discrepancy:
> `"\"author\": \"Stephen P. Lutar Jr.\", \"organization\": \"SZL Consulting LTD\""` — differs from all CITATION.cff files which use `SZL Holdings`.

**`pin-check.yml`** — intra-org exemption:
> `"# Reusable workflows live in this org and may use @main — allow that"` → `"[[ \"$ref\" == szl-holdings/* ]] && continue"`

---

## Doctrine Compliance Summary

| Pattern | Files Scanned | Hits |
|---|---|---|
| AlloyScape | All accessible source + docs | 0 |
| Glass Wing / Glasswing | All accessible source + docs | 0 |
| Mythos | All accessible source + docs | 0 |
| Stephen Paul | All accessible source + docs | 0 |
| Perplexity Computer | All accessible source + docs | 0 |
| anonymous (as a pattern) | All accessible source + docs | 0 |

**All clear on Doctrine V6 forbidden-pattern check.**

---

*End of PhD Dev Pod Engineering Audit Report — SZL Holdings*  
*Evidence anchored to `gh api /repos/szl-holdings/{repo}/...` read-only calls.*  
*No PRs opened. No pushes made. Read-only audit.*
