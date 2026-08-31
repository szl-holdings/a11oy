# Contributing to A11oy

Thanks for your interest. This repository is part of the [SZL Holdings](https://github.com/szl-holdings) platform — physics-grounded, governed AI decision infrastructure for regulated environments. A11oy is published source-available so it can be audited, evaluated, deployed into air-gapped environments (UDS / Zarf), and forked by partners.

This document is the **single source of truth** for how to contribute. Two lanes exist; pick the one that matches your change.

---

## Two contribution lanes

### Lane A — Community-open surface (PRs welcome, no prior agreement)

PRs are accepted for the following directories without a partnership agreement, under the DCO terms below:

| Surface | What lives there |
|---|---|
| `artifacts/a11oy-uds/` | The UDS/Zarf payload, build scripts, deploy manifests, doctrine demo |
| `docs/` | Public-facing documentation (architecture, security, UDS-bundle, forking, runbooks) |
| `.github/`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `GOVERNANCE.md`, `ROADMAP.md` | Repo governance files |
| Smoke tests against the **public release URL** | `scripts/smoke-*` and equivalent |
| `examples/`, `samples/`, `tutorials/` | New worked examples that exercise the shipped doctrine |
| Bug fixes to anything above | Including correctness fixes to formulas / data tables |

If a downstream consumer (e.g. Defense Unicorns) forks A11oy into their own org to re-sign and republish as their own UDS package, the entire `artifacts/a11oy-uds/` tree, this `CONTRIBUTING.md`, and the doctrine demo are intentionally structured to make that fork productive on day one. See [`docs/FORKING.md`](./docs/FORKING.md).

### Lane B — Core proprietary surface (coordinated only)

`packages/a11oy-core/` and `packages/a11oy-connection/` contain the proprietary doctrine implementation. Drive-by PRs touching these files will be closed with a pointer to this section. To contribute here:

1. Open an issue describing what you want to change and **why** (cite the relevant physics or the failing observation).
2. Wait for a maintainer to label it `core:accept-pr`. We will tell you within 7 days if a PR is wanted.
3. Then open the PR.

This is not about gatekeeping — it's because changes here can silently violate doctrine invariants (POVM completeness, KS-18 2-cover, Bohr floor) in ways that a smoke test catches but a code review easily misses. We want to be in the loop **before** you spend the time.

---

## Doctrine pre-flight checklist (REQUIRED for any PR touching `packages/a11oy-core/`)

Every PR that touches the doctrine code MUST keep these invariants green. CI runs them; if they fail, the PR will not merge.

1. **POVM completeness.** For every constructed POVM, `Σ E_i = I` to within `1e-9`.
2. **KS-18 2-regular cover.** Each of the 18 vector indices appears in **exactly 2** of the 9 contexts. Verified by `Σ_ctx Σ_v 1[v∈ctx] = 36` and `∀v: count(v) == 2`.
3. **KS-18 unsatisfiability.** Exhaustive `{0,1}^18` search returns 0 assignments where every context sums to 1.
4. **Tetrad orthonormality.** Frame vectors satisfy `⟨e_i, e_j⟩ = δ_ij` to within `1e-9`.
5. **Bohr complementarity floor.** For any conjugate pair (A,B) at maximum admissible noise, `σ_A · σ_B ≥ 0.25 − ε`.
6. **Fisher–Rao metric.** `d(p,p) = 0`, `d(p,q) = d(q,p)`, triangle inequality on random simplex samples, and reduces to `2·arccos(Σ√(p_i q_i))` on the simplex.

**Why these and not "the tests pass":** unit tests can drift; these six properties are the contract. If you break one, A11oy stops being A11oy regardless of what the rest of the suite says.

Run them locally before opening the PR:

```bash
pnpm -F @a11oy/core test:doctrine
node dist/a11oy-uds/doctrine-demo.mjs <core-dir> <conn-dir>
bash scripts/smoke-from-public-url.sh
```

---

## DCO sign-off (REQUIRED on every commit)

Every commit must be signed off under the [Developer Certificate of Origin 1.1](https://developercertificate.org/). The DCO is a lightweight per-commit attestation that you wrote the code or have the right to contribute it. Use `git commit -s` to add the trailer automatically:

```
Signed-off-by: Real Name <real-email@example.com>
```

PRs without a DCO sign-off on every commit will be blocked by CI. We use DCO instead of a CLA so individuals can contribute without paperwork.

By signing off you also grant the project the license terms in [`LICENSE`](./LICENSE) for the contributed change.

---

## How to open a good PR

1. **Open the issue first** if the change is non-trivial (more than ~30 lines or any user-visible behavior change). Drive-by refactors will be asked to start with an issue.
2. **One logical change per PR.** No "and while I was in there..." commits.
3. **Tests.** New behavior gets a test. Bug fixes get a regression test that fails on `main` and passes with the PR.
4. **Doctrine demo.** If you touched anything in `packages/a11oy-core/` or `packages/a11oy-connection/`, run `node doctrine-demo.mjs` against the rebuilt dist and paste the output in the PR body.
5. **Conventional commit subject line.** `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `perf:`, `build:`. Keep the subject ≤ 72 chars.
6. **Update `CHANGELOG.md`** under `## [Unreleased]` if your change is user-visible.

The PR template will walk you through this.

---

## Issues

Use the issue templates — they exist so you don't have to guess what we need:

- **Bug report** — something that worked is now broken, or something doesn't match the docs / paper citation.
- **Feature request** — something new you'd like to be able to do.
- **Doctrine question** — you think a formula, derivation, or invariant is wrong. These are first-class — please file them.
- **Security disclosure** — see [`SECURITY.md`](./SECURITY.md). **Do not open a public issue for vulnerabilities.**

---

## Code of Conduct

By participating you agree to the [Code of Conduct](./CODE_OF_CONDUCT.md). We follow Contributor Covenant 2.1. The project lead is the enforcement contact: `stephen@szlholdings.com`.

---

## Governance and decision-making

See [`GOVERNANCE.md`](./GOVERNANCE.md) for who decides what, the review SLA, and how the maintainer roster changes.

For a snapshot of where the project is going next, see [`ROADMAP.md`](./ROADMAP.md).

---

## Quick links

| If you want to... | Go to |
|---|---|
| Report a bug | [New issue → Bug report](../../issues/new?template=bug_report.yml) |
| Suggest a feature | [New issue → Feature request](../../issues/new?template=feature_request.yml) |
| Challenge a formula or derivation | [New issue → Doctrine question](../../issues/new?template=doctrine_question.yml) |
| Disclose a vulnerability | [`SECURITY.md`](./SECURITY.md) |
| Fork A11oy into your own UDS catalog | [`docs/FORKING.md`](./docs/FORKING.md) |
| Verify a published release | [`OPERATOR-QUICKSTART.md`](https://github.com/szl-holdings/a11oy/releases/latest) |

---

## Repository architecture (the showcase substrate)

The lanes above govern the proprietary `packages/a11oy-core/` surface. Most of the live
application, though, is the **flat-rooted Python showcase substrate** beside `serve.py`
(~222 `a11oy_*.py` / `szl_*.py` modules). The full map is in
[`docs/architecture.md`](./docs/architecture.md); the essentials for a contributor:

### Run it locally

```bash
git clone https://github.com/szl-holdings/a11oy.git && cd a11oy
pip install -r requirements.txt
PORT=7860 uvicorn serve:app --host 0.0.0.0 --port 7860 --reload
# then open http://127.0.0.1:7860/console  (the orchestrator console)
```

### The `register()` pattern

`serve.py` is the boot entry and route-assembly point. A user-visible surface is a
self-contained module beside `serve.py` that exposes a top-level
`register(app, ns="a11oy")` function. `serve.py` imports it (try/except-guarded so a
missing optional module degrades honestly instead of crashing the Space) and calls:

```python
_szl_<name>.register(app, ns="a11oy")   # adds routes; returns an honest status dict
```

**Ordering is load-bearing:** every `register(...)` call must run **before** the SPA
catch-all (`/{path} -> index.html`). FastAPI matches routes in declaration order, so a
surface registered after the catch-all is shadowed by the SPA and 404s client-side.
Nav-injection modules (e.g. `a11oy_nav_wireup.py`) insert their middleware at index `0`
for the same reason.

### Byte-identical shared modules

Many `szl_*.py` (and a few `a11oy_*.py`, e.g. `a11oy_hf_assets.py`) modules are vendored
into **both** a11oy and killinchu and must stay **byte-identical**. If you edit a shared
module in one repo, make the *identical* edit in the sibling repo in the same change —
**including comment and docstring edits**. The `shared-file-drift` CI guard fails the build
on any new divergence; deliberate, documented exceptions live in
`.github/shared-file-drift-allow.txt`.

### Doctrine hard-gates (CI will not let you weaken these)

- **`locked = 8`** — exactly 8 locked-proven formulas `{F1,F4,F7,F11,F12,F18,F19,F22}`. Never inflate the count (machine-enforced `locked_count_eight`).
- **Λ = Conjecture 1** — Λ-uniqueness is a conjecture, never described as a theorem.
- **No user-visible codenames** and no marketing-superlative tokens — enforced by the `doctrine-grep.yml` banned-token gate (`.doctrine-allowlist` is the only opt-out); factual claims need an adjacent citation.
- **Never commit a key** — `gitleaks.yml` blocks secrets; receipts are clearly UNSIGNED when `SZL_COSIGN_PRIVATE_PEM` is absent.

### How the CI guards work

Guards run on every PR and push to `main`. Beyond the doctrine pre-flight above, key showcase
guards include: `doctrine-grep.yml` (banned-token scan), `shared-file-drift.yml` (shared
modules identical across a11oy + killinchu), `copy-sync-lockstep-guard.yml` (every module
`serve.py` imports is in the Dockerfile COPY set **and** the HF mirror set),
`overclaim-guard.yml`, `gitleaks.yml`, `dco.yml` (sign-off), `ci.yml`, `codeql.yml`,
`scorecard.yml`, `slsa-build.yml`. If a guard trips on a comment or doc you added, **fix
your text — never weaken the gate.**

— A11oy maintainers
