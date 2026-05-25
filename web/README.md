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

## Governance & audit

- Machine gap audit (latest pass, 2026-05-05): [`docs/audits/machine-gap-audit.md`](../../docs/audits/machine-gap-audit.md)
- Best-of-breed adoption survey: [`docs/research/best-of-breed-adoption.md`](../../docs/research/best-of-breed-adoption.md)
- Operations governance hub (in-app): [`/a11oy/operations/alloy-governance`](src/pages/operations/alloy-governance.tsx)

---

**SZL Holdings** · [szlholdings.com](https://szlholdings.com) · [inquiries@szlholdings.com](mailto:inquiries@szlholdings.com)
