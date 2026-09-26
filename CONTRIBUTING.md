# Contributing to A11oy

Thanks for your interest. This repository is part of the [SZL Holdings](https://github.com/szl-holdings) platform — physics-grounded, governed AI decision infrastructure for regulated environments. A11oy is published source-available so it can be audited, evaluated, deployed into air-gapped environments (UDS / Zarf), and forked by partners.

This document is the **single source of truth** for how to contribute. Two lanes exist; pick the one that matches your change.

This is a solo-build. There is no co-signer. DCO / `Signed-off-by` trailers are not required and are not a merge gate.

---

## Two contribution lanes

### Lane A — Community-open surface (PRs welcome, no prior agreement)

PRs are accepted for the following directories without a partnership agreement:

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

---

## Doctrine pre-flight checklist (REQUIRED for any PR touching `packages/a11oy-core/`)

Every PR that touches the doctrine code MUST keep these invariants green. CI runs them; if they fail, the PR will not merge.

1. **POVM completeness.** For every constructed POVM, `Σ E_i = I` to within `1e-9`.
2. **KS-18 2-regular cover.** Each of the 18 vector indices appears in **exactly 2** of the 9 contexts.
3. **KS-18 unsatisfiability.** Exhaustive `{0,1}^18` search returns 0 assignments where every context sums to 1.
4. **Tetrad orthonormality.** Frame vectors satisfy `⟨e_i, e_j⟩ = δ_ij` to within `1e-9`.
5. **Bohr complementarity floor.** For any conjugate pair (A,B) at maximum admissible noise, `σ_A · σ_B ≥ 0.25 − ε`.
6. **Fisher–Rao metric.** `d(p,p) = 0`, `d(p,q) = d(q,p)`, triangle inequality on random simplex samples.

Run them locally before opening the PR:

```bash
pnpm -F @a11oy/core test:doctrine
node dist/a11oy-uds/doctrine-demo.mjs <core-dir> <conn-dir>
bash scripts/smoke-from-public-url.sh
```

---

## How to open a good PR

1. **Open the issue first** if the change is non-trivial.
2. **One logical change per PR.**
3. **Tests.** New behavior gets a test. Bug fixes get a regression test.
4. **Doctrine demo** if you touched `packages/a11oy-core/` or `packages/a11oy-connection/`.
5. **Conventional commit subject line.** `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `perf:`, `build:`.
6. **Update `CHANGELOG.md`** under `## [Unreleased]` if user-visible.

No `Signed-off-by` trailer is required.

---

## Issues

Use the issue templates.

- **Bug report**
- **Feature request**
- **Doctrine question**
- **Security disclosure** — see [`SECURITY.md`](./SECURITY.md). **Do not open a public issue for vulnerabilities.**

---

## Code of Conduct

By participating you agree to the [Code of Conduct](./CODE_OF_CONDUCT.md). Project lead: `stephen@szlholdings.com`.

---

## Governance

See [`GOVERNANCE.md`](./GOVERNANCE.md) and [`ROADMAP.md`](./ROADMAP.md).

---

## Doctrine hard-gates (CI will not let you weaken these)

- **`locked = 8`** — exactly 8 locked-proven formulas `{F1,F4,F7,F11,F12,F18,F19,F22}`.
- **Λ = Conjecture 1** — never described as a theorem.
- **No user-visible codenames** — `doctrine-grep.yml`.
- **Never commit a key** — `gitleaks.yml`.

DCO is not a gate. There is no active root `.github/workflows/dco.yml` on this repository.
