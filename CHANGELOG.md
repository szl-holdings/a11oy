# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Restored the KS-18 witness to the release-aligned 2-regular parity cover and added a regression test for empty-observation unsatisfiability.

### Added
- Standalone doctrine workspace wiring with root `test:doctrine`, `typecheck:doctrine`, and `build:doctrine` scripts for the `@a11oy/core` / `@a11oy/connection` packages.
- Doctrine Build GitHub Action for package tests, typechecks, builds, and payload manifest verification.
- Deterministic deploy payload manifest tooling plus `deploy/MANIFEST.json`.
- Hugging Face payload preparation and manual publish workflow using `HF_TOKEN`.
- Series-A presentation pass: SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, CODEOWNERS
- Apache-2.0 LICENSE
- CITATION.cff for independent citation

## Release index

Releases are tagged on this repository. See [GitHub Releases](../../releases) for the full list.
