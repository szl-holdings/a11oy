# SZL Holdings repository map

This map organizes the public `szl-holdings` GitHub organization around the
current build center: `a11oy`, the vertical alignment substrate. It is intended
to be the first navigation layer before pulling code from sibling repositories.
The categorized tables are a curated snapshot of **active** repositories; use the
clone helper to discover the live GitHub inventory as it changes. Repositories
that have been retired or consolidated into `a11oy` are listed separately at the
end and should not be cloned.

## Build center

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`a11oy`](https://github.com/szl-holdings/a11oy) | Vertical alignment substrate: policy, measurement, knowledge, and QEC-integrity packages for governed AI execution. | `main` | TypeScript |

## Runtime and composition layer

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`platform`](https://github.com/szl-holdings/platform) | Composing monorepo for the Ouroboros runtime, Lutar formulas, dual-witness adapters, agent tooling, and CI substrate. | `main` | TypeScript |
| [`ouroboros`](https://github.com/szl-holdings/ouroboros) | Ouroboros runtime for formulas, agentic loops, Bekenstein bounds, and dual-witness emitters. | `main` | TypeScript |

## Formal substrate and thesis

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`lutar-lean`](https://github.com/szl-holdings/lutar-lean) | Lean 4 + Mathlib kernel proofs for the governance framework, including Lambda-gate theorems and audit-fiber invariants. | `main` | Lean |

The formal thesis (formerly the `ouroboros-thesis` repo) is now published via Zenodo
DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276); its Lean kernel
lives in [`lutar-lean`](https://github.com/szl-holdings/lutar-lean).

## Receipts, telemetry, and adapters

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`uds-mesh`](https://github.com/szl-holdings/uds-mesh) | Unified Data System span schemas and governance receipts for OTEL-style observability. | `main` | Shell |
| [`vsp-otel`](https://github.com/szl-holdings/vsp-otel) | OpenTelemetry exporter for SZL audit fibers and Lambda-axis spans. | `main` | TypeScript |

The receipt-minting, receipt-orchestration, and drift-detection verticals (internal
codenames `amaru`, `rosie`, `sentra`) are consolidated into `a11oy` — see the
retired/consolidated section below.

## Trust, knowledge transfer, and organization operations

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`szl-trust`](https://github.com/szl-holdings/szl-trust) | Public Trust Portal for Covenant Proof Standard run artifacts and deterministic replay. | `main` | Not yet classified |
| [`szl-cookbook`](https://github.com/szl-holdings/szl-cookbook) | Recipes for building governed AI systems on the SZL substrate. | `main` | TypeScript |
| [`szl-brand`](https://github.com/szl-holdings/szl-brand) | Brand assets, logos, social-preview templates, and visual doctrine. | `main` | Python |
| [`.github`](https://github.com/szl-holdings/.github) | Organization profile and community health files. | `main` | Not yet classified |

## Retired and consolidated repositories

These earlier repositories have been retired or folded into `a11oy`. They are listed
for provenance only; they are **not** active repositories and cannot be cloned.

| Former repo | Status | Where it lives now |
| --- | --- | --- |
| amaru | Consolidated into `a11oy` | a11oy **Memory** vertical — Cardano-anchored governance-receipt minting and Shor-encoded provenance. |
| rosie | Consolidated into `a11oy` | a11oy **Operator** vertical — receipt-DAG orchestration; summation invariant proven in [`lutar-lean`](https://github.com/szl-holdings/lutar-lean). |
| sentra | Consolidated into `a11oy` | a11oy **Sentinel** vertical — telemetry adapter and Kitaev-surface drift detection. |
| ouroboros-thesis | Retired repo | Published via Zenodo DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276); Lean kernel in [`lutar-lean`](https://github.com/szl-holdings/lutar-lean). |
| vessels · counsel · terra · carlota-jo | Retired | Product/vertical scaffolds, not currently public. |
| agi-forecast | Retired | Forecasting / scenario scaffold, not currently public. |

## Local workspace checkout

Use the helper below to discover, clone, or refresh sibling repositories
without mixing their source trees into this repository:

```bash
bash scripts/clone-org-repos.sh
```

When the GitHub CLI is authenticated, the helper asks GitHub for the live repo
list and filters archived repositories and forks by default. Without `gh`, it
falls back to the curated snapshot above. By default, the helper checks out repos
under `.repos/szl-holdings/`, which is ignored by git. Override the destination
if you want the checkouts elsewhere:

```bash
DEST="$HOME/src/szl-holdings" bash scripts/clone-org-repos.sh
```

Useful options:

```bash
INCLUDE_ARCHIVED=1 bash scripts/clone-org-repos.sh
INCLUDE_FORKS=1 bash scripts/clone-org-repos.sh
UPDATE_WORKTREE=0 bash scripts/clone-org-repos.sh
REMOTE_PROTOCOL=ssh bash scripts/clone-org-repos.sh
```

## Working rule

- Build substrate packages and shared docs here in `a11oy`.
- Pull sibling repos into `.repos/szl-holdings/` for cross-repo reading,
  integration testing, or later coordinated PRs.
- Do not vendor sibling source trees into `a11oy` unless a specific package is
  intentionally being migrated into this repository.
