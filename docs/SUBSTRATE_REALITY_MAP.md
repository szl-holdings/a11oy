# SZL substrate reality map

This page turns the screenshot substrate maps into reviewable evidence. It keeps
the useful framing, but it does not promote a claim unless the claim has a public
repo, release, workflow, DOI, or checked-in file behind it.

Deployment ownership is tracked separately in
[`REPLIT_STATE_PLANE_CONTINUITY.md`](REPLIT_STATE_PLANE_CONTINUITY.md). In
particular, the public `a11oy.net` GitHub Pages site, the `a-11-oy.com` product,
and the Replit `Unified Control Hub` are three independent state planes. A task
marker or deployment on one plane is not evidence for either of the others.

## Evidence legend

| Status | Meaning |
| --- | --- |
| `verified-public` | Verified from public GitHub metadata, public release metadata, DOI links, or files in this repo. |
| `verified-ci` | Verified from a visible GitHub workflow/check result. |
| `owner-api-needed` | Plausible owner-side claim, but this runtime cannot verify it because the GitHub API requires privileged security/admin scope. |
| `open-pr-not-main` | Exists as an open PR or branch, not merged main behavior. |
| `narrative-map` | Useful positioning or brand/anatomy framing, not a shipped runtime claim. |

## Substrate spine — real public repos

| Repo | Role in the spine | Public evidence | Status | Caveat |
| --- | --- | --- | --- | --- |
| `ouroboros-thesis` | Thesis / math substrate | Public repo and DOI `10.5281/zenodo.20434276`; concept DOI `10.5281/zenodo.19944926` | `verified-public` | Latest public GitHub release observed here is `paper-v17-1.0.0`; v18 is DOI-pinned but GitHub release reconciliation remains open. |
| `lutar-lean` | Lean proof substrate | Public repo, release `lutar-v18.0.0`, DOI `10.5281/zenodo.20434308` | `verified-public` | Canonical @ `3de37e5` (2026-05-31): **752 declarations, 15 axioms (14 unique), 160 sorries** (109 baseline + 51 Putnam) — per [`lean_numbers.json`](https://github.com/szl-holdings/.github/blob/main/.github/data/lean_numbers.json). Prior Agent C figure (626 / 189) was pre-reproducibility-script and is retired. |
| `ouroboros` | Runtime substrate | Public repo, release `v6.3.0` | `verified-public` | Treat runtime-specific performance claims as per-release/per-paper evidence, not blanket current-main facts. |
| `a11oy` | Governed execution hub | This repo, green PR #139 checks, receipt/payload/doctrine tests | `verified-ci` | Main currently has seven policy gate files and ten theorem-runtime manifest entries; larger gate counts are PRs until merged. |
| `amaru` | Memory / receipt anchoring organ | Public repo, release line visible from GitHub metadata | `verified-public` | Current packet cites it as supporting substrate, not independently validated runtime in this checkout. |
| `rosie` | Receipt orchestration / observability organ | Public repo, release line visible from GitHub metadata | `verified-public` | Current packet cites it as supporting substrate, not independently validated runtime in this checkout. |
| `sentra` | Drift/security / vertical intelligence organ | Public repo, release line visible from GitHub metadata | `verified-public` | Current packet cites it as supporting substrate; CodeQL/security alert counts require privileged API access. |

## Thirteen public substrate repos

These 13 are real public repos observed through GitHub metadata and used as the
frontier capability set. Capability text should track each repo's own README or
description, not invented marketing copy.

| # | Repo | Evidence-backed capability line |
| --- | --- | --- |
| 1 | `a11oy` | Governed execution fabric / policy, measurement, knowledge, QEC integrity, receipts, and payload discipline. |
| 2 | `amaru` | Memory and receipt-anchoring substrate; supporting component for provenance claims. |
| 3 | `rosie` | Receipt orchestration and body-graph observability component. |
| 4 | `sentra` | Security, sanctions/dark-vessel, drift, and policy-gated intelligence component. |
| 5 | `ouroboros` | Bounded-loop runtime and formula substrate. |
| 6 | `lutar-lean` | Lean 4 / Mathlib proof substrate for scoped theorem claims. |
| 7 | `ouroboros-thesis` | DOI-pinned thesis and public claim taxonomy. |
| 8 | `uds-mesh` | UDS span schemas and DSSE governance receipt mesh. |
| 9 | `vsp-otel` | OpenTelemetry exporter for audit fibers and Lambda-axis spans. |
| 10 | `agi-forecast` | Forecast / competition-math benchmark harness with honest `1/12` baseline posture. |
| 11 | `platform` | Composition monorepo for deployed runtime surfaces. |
| 12 | `szl-brand` | Brand, anatomy, social preview, and visual doctrine assets. |
| 13 | `szl-cookbook` | Recipes and how-to guides for governed AI infrastructure. |

## Four-quadrant substrate map

This is a classification map, not a maturity claim.

| Quadrant | Repos | Evidence-backed reading |
| --- | --- | --- |
| Math substrate | `ouroboros-thesis`, `lutar-lean`, `agi-forecast` | Thesis DOI, Lean proof substrate DOI/release, and benchmark/forecast harness. |
| Agentic substrate | `ouroboros`, `amaru`, `rosie`, `a11oy` | Runtime, receipt, memory, and governed execution components. |
| Observability + cyber | `sentra`, `uds-mesh`, `vsp-otel` | Security/drift component, UDS span schemas, and OTel exporter. |
| Sovereign-AI generation | `platform`, `szl-cookbook`, `szl-brand` | Product composition, recipes, and brand/anatomy/public surface assets. |

## Anatomy / organ map

The body/anatomy view is useful for storytelling, but it must stay labeled as a
brand architecture map unless the specific row points to code, tests, or release
evidence.

| Organ label | Repo / system | Status | Evidence boundary |
| --- | --- | --- | --- |
| Brain / memory | `amaru` | `narrative-map` + public repo | Use as a memory/attestation metaphor unless citing an exact Amaru release/test. |
| Heart / pulse | `ouroboros` | `verified-public` | Runtime repo and release exist; exact module counts need repo-local evidence. |
| Blood / receipt flow | `rosie`, `uds-mesh`, `a11oy` | `verified-public` | Receipt and UDS framing is supported by public repos and A11oy receipt tests. |
| Immune / security gates | `sentra`, `a11oy` | `verified-public` | Security/drift repo exists; exact assertion counts require repo-local test logs. |
| Skeleton / proofs | `lutar-lean`, `ouroboros-thesis` | `verified-public` | Proof/thesis repos and DOIs exist; do not overstate current sorry closure. |
| Nervous / telemetry | `vsp-otel` | `verified-public` | Public OTel exporter repo and release exist. |
| Wires / cross-component mesh | `uds-mesh` | `verified-public` | UDS span schema repo exists; deployment claims need release/pull evidence. |

## GHAS / security posture

| Screenshot claim | Reality status from this runtime |
| --- | --- |
| `a11oy#138` GHAS badge update is live green | `verified-ci`: PR #138 is open, mergeable, and all visible checks are success. |
| 16 public repos have secret scanning, push protection, and Dependabot enabled | `owner-api-needed`: this token cannot read org/repo security settings. Do not repeat as verified unless owner/API evidence is attached. |
| 30 CodeQL alerts open on a11oy (verified Agent C 2026-05-30) | `owner-api-needed`: 403 from code-scanning API; Agent C queried alerts directly. |
| 8 Dependabot alerts total | `owner-api-needed`: Dependabot/security alert counts require privileged API access. |
| Two SLSA L3 PRs opened with real `slsa-framework/slsa-github-generator` workflows | `open-pr-not-main`: PRs exist, but `a11oy#137` has failing DCO/tests and `lutar-lean#117` has failing DCO/DOI-title gate in the observed checks. |

## Claim boundary checklist

Use this language until the upstream evidence changes:

- **Thesis v18:** DOI-pinned and valid for citation; GitHub release still needs
  v18 reconciliation.
- **Lean proofs:** proof substrate and green kernel-check PRs exist, but the
  repo description still carries tracked sorries/placeholders. Cite exact
  modules and CI, not “all closed”.
- **A11oy gates:** PR #140 may make the broader gate set real when merged; this
  packet should not describe G36-G40 or 35/40-gate totals as main until merged.
- **SLSA:** L3 work is PR/roadmap until failing PRs are signed, green, merged,
  and release assets are produced.
- **GHAS:** badge/dashboard work can be linked when public; org-wide settings
  require owner-side API evidence.
