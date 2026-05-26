<!--
Thanks for opening a PR! Please fill in every section below.
PRs missing the doctrine checklist or DCO sign-off will be blocked.
-->

## Summary

<!-- 1–3 sentences. What does this change do and why. -->

## Lane

- [ ] **Lane A** (community-open: `artifacts/a11oy-uds/`, `docs/`, `.github/`, governance files, smoke tests, examples, bug fixes)
- [ ] **Lane B** (core proprietary: `packages/a11oy-core/` or `packages/a11oy-connection/` — confirm the issue is labelled `core:accept-pr`)

## Linked issue

Fixes #<!-- issue number -->

## Type

- [ ] Bug fix
- [ ] New feature
- [ ] Doctrine fix (formula / data / invariant)
- [ ] Documentation
- [ ] Build / CI / tooling
- [ ] Refactor (no behavior change)

## Doctrine pre-flight checklist

<!-- REQUIRED if this PR touches packages/a11oy-core/ or packages/a11oy-connection/. -->
<!-- Strike through items that genuinely do not apply and say why. -->

- [ ] POVM completeness: `Σ E_i = I` within 1e-9 for all constructed POVMs
- [ ] KS-18 2-regular cover preserved: every vector index appears in exactly 2 of 9 contexts
- [ ] KS-18 unsatisfiability: exhaustive `{0,1}^18` search returns 0 satisfying assignments
- [ ] Tetrad orthonormality: `⟨e_i, e_j⟩ = δ_ij` within 1e-9
- [ ] Bohr complementarity floor: `σ_A · σ_B ≥ 0.25 − ε` on the worst-case conjugate pair
- [ ] Fisher–Rao metric: zero, symmetry, triangle inequality, simplex closed form
- [ ] `node doctrine-demo.mjs` against the rebuilt dist shows the expected verdict table

If you skipped any item, explain why here:
<!-- ... -->

## Tests

- [ ] New behavior has a unit test
- [ ] Bug fix has a regression test that failed on `main` and passes with this PR
- [ ] `pnpm -F @a11oy/core test:doctrine` is green locally
- [ ] `bash scripts/smoke-from-public-url.sh` is green locally (for release-affecting PRs)

## Documentation

- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] Public docs (`docs/`, `README.md`) updated where behavior changed
- [ ] Code comments updated where a non-obvious invariant changed

## Backward compatibility

- [ ] No public API change
- [ ] Public API change — migration note added to `CHANGELOG.md`
- [ ] UDS package layout change — `MANIFEST.json` and `OPERATOR-QUICKSTART.md` updated

## DCO sign-off

- [ ] Every commit in this PR has a `Signed-off-by:` trailer (use `git commit -s`)

## Reviewer notes

<!-- Anything reviewers should look at first, edge cases, deliberate non-goals, etc. -->
