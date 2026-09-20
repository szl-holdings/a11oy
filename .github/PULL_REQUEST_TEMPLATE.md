<!--
Thanks for opening a PR. Fill in the sections below.
DCO / Signed-off-by is not required. Solo-build. No co-signer gate.
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

- [ ] POVM completeness
- [ ] KS-18 2-regular cover preserved
- [ ] KS-18 unsatisfiability
- [ ] Tetrad orthonormality
- [ ] Bohr complementarity floor
- [ ] Fisher–Rao metric
- [ ] doctrine-demo against rebuilt dist

## Tests

- [ ] New behavior has a unit test
- [ ] Bug fix has a regression test
- [ ] doctrine tests green locally where applicable

## Documentation

- [ ] CHANGELOG updated if user-visible

## Reviewer notes

<!-- Anything reviewers should look at first. -->
