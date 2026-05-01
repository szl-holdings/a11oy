# A11oy — Brand Orchestration Layer

  > Cross-domain AI agent fabric and brand intelligence system — the orchestration backbone connecting all SZL Holdings domain packs.

  [![CI](https://github.com/szl-holdings/szl-holdings-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/szl-holdings-platform/actions/workflows/ci.yml)
  [![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
  [![Gov Readiness](https://img.shields.io/badge/NYSTEC%20readiness-72%2F100-2da44e?style=flat-square)](https://github.com/szl-holdings/ouroboros/blob/main/docs/audit/szl-government-readiness.md)
[![License](https://img.shields.io/badge/license-Proprietary-red?style=flat-square)](../../LICENSE.md)

  [Live Demo](https://szlholdings.com) · [Platform Demo Video](https://szlholdings.com/szl-demo-video/) · [Investor Dashboard](https://szlholdings.com/stephen/investor) · [Architecture](../../docs/architecture/architecture.md)

  ![A11oy — Brand Orchestration Layer](https://raw.githubusercontent.com/szl-holdings/szl-holdings-platform/master/.github/assets/screenshots/a11oy-hero.jpg)

  ---
  ## What it does

  A11oy is the **orchestration control plane** of the SZL Holdings platform — the agent ecosystem brain that routes tasks, enforces governance, powers Sentra and Amaru, and manages the Ouroboros loop kernel. Every agentic action taken anywhere in the platform routes through the Alloy Fabric. A11oy is where operators monitor, tune, and govern that activity.

  ## Government readiness — 72/100

  April 30, 2026 NYSTEC pre-briefing audit. Strong on governance, proof, and traceability; gaps in certification path and formal documentation.

  | Capability | Government alignment |
  |---|---|
  | Append-only trace runtime | GSA audit trail / DoD Traceable tenet |
  | Decision receipt system | Produce-evidence-on-demand requirements |
  | Ouroboros loop with delta/consistency gates | DoD Reliable + Governable tenets |
  | Human approval gate at R3/R4 risk tiers | GSA human oversight / DoD Responsible tenet |
  | Validator registry with hard stops | NIST AI RMF MANAGE function |
  | Replay/golden run verification | Audit reproducibility requirements |
  | Domain pack routing | NIST AI RMF MAP function |
  | Primary-source hash chain (Katzilla) | GSA RAG source attribution requirement |

  **Open gaps** (documentation, no architectural rework): FedRAMP authorization disclosure, CMMC/NIST SP 800-171 gap assessment, bias-testing methodology, US-only data residency statement, 72-hour incident response procedure.

  ## Run locally

  ```bash
  pnpm install
  pnpm --filter @workspace/api-server dev   # API server first
  pnpm --filter @workspace/a11oy dev
  ```

  **Primary route:** `/a11oy/`

  ## Key modules

  | Module | Route | Purpose |
  |---|---|---|
  | Agent Registry | `/a11oy/` | Active agent status across all domains |
  | Covenant Policies | `/a11oy/policies` | Policy configuration and override management |
  | Brand Intelligence | `/a11oy/brand` | Cross-domain brand signal monitoring |
  | Alloy Actions | `/a11oy/actions` | Pending and completed agentic actions |
  | Proof Chain | `/a11oy/proof-chain` | Immutable audit trail viewer |

  ## Tech stack

  React 19 + Vite 7 + TypeScript (strict) · Express 5 (shared API server) · PostgreSQL 16 / Drizzle ORM · Multi-provider AI (Anthropic, OpenAI, Gemini) · OIDC/PKCE auth · Proof Chain audit trail
  
  ---

  **SZL Holdings** · [szlholdings.com](https://szlholdings.com) · [inquiries@szlholdings.com](mailto:inquiries@szlholdings.com)

  ---
  ## About this repository

  This is a public showcase of one product in the [SZL Holdings platform](https://github.com/szl-holdings/szl-holdings-platform) monorepo. It mirrors the README from the platform artifact directory; the canonical, version-controlled source — including the React app, tests, and infrastructure — lives in the platform repo.

  All seven products share the same governed substrate:

  - **[`@workspace/ouroboros`](https://github.com/szl-holdings/ouroboros)** — bounded loops with measurable convergence, v6 ecosystem layer, government readiness module (**142/142 tests**)
  - **[`@workspace/codex-kernel`](https://github.com/szl-holdings/szl-holdings-platform/tree/master/packages/codex-kernel)** — decision receipts, validators, replay, trace-hash verification
  - **The Ouroboros Thesis** — [`szl-holdings/ouroboros-thesis`](https://github.com/szl-holdings/ouroboros-thesis) — architectural rationale + v6 operational contract

  Government readiness audit (NYSTEC pre-briefing, 2026-04-30): [`docs/audit/szl-government-readiness.md`](https://github.com/szl-holdings/ouroboros/blob/main/docs/audit/szl-government-readiness.md)

  © 2026 SZL Holdings. All rights reserved.
  