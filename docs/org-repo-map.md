# SZL Holdings repository map

This map organizes the public `szl-holdings` GitHub organization around the
current build center: `a11oy`, the vertical alignment substrate. It is intended
to be the first navigation layer before pulling code from sibling repositories.

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
| [`ouroboros-thesis`](https://github.com/szl-holdings/ouroboros-thesis) | DOI-pinned thesis substrate for formal AI governance through Lambda-axis scoring, audit fibers, and provable receipts. | `main` | Lean |

## Receipts, telemetry, and adapters

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`amaru`](https://github.com/szl-holdings/amaru) | Cardano-anchored governance receipt minting and Shor-encoded provenance. | `main` | TypeScript |
| [`rosie`](https://github.com/szl-holdings/rosie) | Receipt orchestration for CSS-ingress and canonical receipt byte-string emission. | `main` | TypeScript |
| [`sentra`](https://github.com/szl-holdings/sentra) | Sensor and telemetry adapter for audit fibers, including Kitaev-surface drift detection. | `main` | TypeScript |
| [`uds-mesh`](https://github.com/szl-holdings/uds-mesh) | Unified Data System span schemas and governance receipts for OTEL-style observability. | `main` | Shell |
| [`vsp-otel`](https://github.com/szl-holdings/vsp-otel) | OpenTelemetry exporter for SZL audit fibers and Lambda-axis spans. | `main` | TypeScript |

## Product and vertical applications

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`vessels`](https://github.com/szl-holdings/vessels) | Maritime fleet intelligence for sanctions screening, dark-vessel detection, ownership graphs, and voyage analytics. | `main` | TypeScript |
| [`counsel`](https://github.com/szl-holdings/counsel) | Legal matter command scaffold for policy-gated AI workflows, document review, obligation mapping, and proof-chain delivery. | `main` | Not yet classified |
| [`terra`](https://github.com/szl-holdings/terra) | Real estate intelligence scaffold for deal-pipeline scoring, portfolio analytics, and AI-assisted underwriting. | `main` | Not yet classified |
| [`carlota-jo`](https://github.com/szl-holdings/carlota-jo) | Private advisory operations scaffold for concierge workflow, proof-chain delivery, and multi-party coordination. | `main` | Not yet classified |

## Trust, knowledge transfer, and organization operations

| Repo | Role | Default branch | Primary language |
| --- | --- | --- | --- |
| [`szl-trust`](https://github.com/szl-holdings/szl-trust) | Public Trust Portal for Covenant Proof Standard run artifacts and deterministic replay. | `main` | Not yet classified |
| [`szl-cookbook`](https://github.com/szl-holdings/szl-cookbook) | Recipes for building governed AI systems on the SZL substrate. | `main` | TypeScript |
| [`szl-brand`](https://github.com/szl-holdings/szl-brand) | Brand assets, logos, social-preview templates, and visual doctrine. | `main` | Python |
| [`agi-forecast`](https://github.com/szl-holdings/agi-forecast) | Forecasting models and scenario library for AI governance trajectories. | `main` | TypeScript |
| [`.github`](https://github.com/szl-holdings/.github) | Organization profile and community health files. | `main` | Not yet classified |

## Local workspace checkout

Use the helper below to clone or refresh sibling repositories without mixing
their source trees into this repository:

```bash
bash scripts/clone-org-repos.sh
```

By default, the helper checks out repos under `.repos/szl-holdings/`, which is
ignored by git. Override the destination if you want the checkouts elsewhere:

```bash
DEST="$HOME/src/szl-holdings" bash scripts/clone-org-repos.sh
```

## Working rule

- Build substrate packages and shared docs here in `a11oy`.
- Pull sibling repos into `.repos/szl-holdings/` for cross-repo reading,
  integration testing, or later coordinated PRs.
- Do not vendor sibling source trees into `a11oy` unless a specific package is
  intentionally being migrated into this repository.
