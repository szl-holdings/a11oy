# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed (`fix/lambda-unification`)
- `runtime/lambda-gate/src/gate.ts` — `computeLambda(axes)` now returns the weighted geometric mean (canonical Λ per thesis v14 §3.3 Definition 2a and `lutar-lean/Lutar/Invariant.lean`). The prior MIN-fold is exposed separately as `weakestAxis(axes)` and surfaced on `EvalResult` as the diagnostic `weakestAxis` field. The gate verdict semantics (per-axis conjunctive AND with thresholds 0.95 critical / 0.90 standard) are unchanged.
- Verified verdict-preserving over a 10,000-vector random scan; no production behaviour change. See `f2_lambda/regression_check.md`.
- Added `docs/lambda-spec.md` as the single source of truth for the Λ scalar vs gate verdict distinction.

### Added
- Series-A presentation pass: SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CODEOWNERS
- Apache-2.0 LICENSE
- CITATION.cff for independent citation

## Release index

Releases are tagged on this repository. See [GitHub Releases](../../releases) for the full list.
