# A11oy — Brand Orchestration Layer

> Cross-domain AI agent fabric and brand intelligence system — the orchestration backbone connecting all SZL Holdings domain packs.

[![CI](https://github.com/szl-holdings/szl-holdings-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/szl-holdings-platform/actions/workflows/ci.yml)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red?style=flat-square)](../../LICENSE.md)

[Live Demo](https://szlholdings.com) · [Platform Demo Video](https://szlholdings.com/szl-demo-video/) · [Investor Dashboard](https://szlholdings.com/stephen/investor) · [Architecture](../../docs/architecture/architecture.md)

![A11oy — Brand Orchestration Layer](../../.github/assets/screenshots/a11oy-hero.jpg)

---

## What it does

A11oy is the Alloy Fabric agent orchestration surface for the SZL Holdings platform. It provides a unified view of all AI agents running across every domain pack — their status, decisions, Covenant Policy gates, and Proof Chain attributions — along with the brand intelligence systems that ensure consistent voice and signal quality across the platform.

Every agentic action taken anywhere in the platform routes through the Alloy Fabric. A11oy is where operators monitor, tune, and govern that activity.

## Run locally

```bash
# From the monorepo root
pnpm install
pnpm --filter @workspace/api-server dev   # Start the API server first
pnpm --filter @workspace/a11oy dev
```

**Primary route:** `/a11oy/`

## Key modules

| Module | Route | Purpose |
|--------|-------|---------|
| Agent Registry | `/a11oy/` | Active agent status across all domains |
| Covenant Policies | `/a11oy/policies` | Policy configuration and override management |
| Brand Intelligence | `/a11oy/brand` | Cross-domain brand signal monitoring |
| Alloy Actions | `/a11oy/actions` | Pending and completed agentic actions |
| Proof Chain | `/a11oy/proof-chain` | Immutable audit trail viewer |

## Tech stack

React 19 + Vite 7 + TypeScript (strict) · Express 5 (shared API server) · PostgreSQL 16 / Drizzle ORM · Multi-provider AI (Anthropic, OpenAI, Gemini) · OIDC/PKCE auth · Proof Chain audit trail

## Architecture reference

Full system architecture: [`docs/architecture/architecture.md`](../../docs/architecture/architecture.md)

---

**SZL Holdings** · [szlholdings.com](https://szlholdings.com) · [inquiries@szlholdings.com](mailto:inquiries@szlholdings.com)


---
## About this repository

This is a public showcase of one product in the [SZL Holdings platform](https://github.com/szl-holdings/szl-holdings-platform) monorepo. It mirrors the README from the platform artifact directory; the canonical, version-controlled source — including the React app, tests, and infrastructure — lives in the platform repo.

All seven products share the same operational substrate:

- **[`@workspace/ouroboros`](https://github.com/szl-holdings/ouroboros)** — bounded loops with measurable convergence; proof-route resolver, risk-tier escalation gate, and almanac cycle advancer.
- **[`@workspace/codex-kernel`](https://github.com/szl-holdings/szl-holdings-platform/tree/main/packages/codex-kernel)** — decision receipts, validators, replay, and trace-hash verification.
- **The Ouroboros Thesis v2** — [`szl-holdings/ouroboros-thesis`](https://github.com/szl-holdings/ouroboros-thesis) — the architectural rationale.

© 2026 SZL Holdings. All rights reserved.
