# GitHub Org Merge Risk — 2026-08-31T21:11:10.083636+00:00

Org: szl-holdings · Method: gh CLI, authenticated, org-wide PR search.

- Repos enumerated: **103** (95 public · 8 private · 35 archived)
- Open PRs org-wide: **0** — merge queue is EMPTY. Nothing to sweep.
- AUTO_ELIGIBLE: 0 · HUMAN_REQUIRED: 0 · BLOCKED_UNKNOWN: 0
- Stale PRs (>30d open): 0

## Context
An org alignment sweep (v14: SECURITY.md, CONTRIBUTING, SHA-pinned CI
templates, forbidden-domain gate, lexicon gates) merged across the org on
2026-08-31, plus CI repair chains in a11oy (#1628–#1633). The queue this
audit exists to classify is currently empty; re-run on any future PR surge.

## RULE
AUTO_ELIGIBLE PRs may be merged without additional sign-off ONLY if this
file, GITHUB_REPO_MATRIX.csv, and the pass receipt are committed first.
HUMAN_REQUIRED and BLOCKED_UNKNOWN PRs are NEVER auto-merged. Any PR
touching receipt schema, verifier, policy engine, capability constitution,
or Flight Recorder is HUMAN_REQUIRED by definition.
