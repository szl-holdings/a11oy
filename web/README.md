# A11oy — Brand Orchestration Layer

> Cross-domain AI agent fabric and brand intelligence system — the orchestration backbone connecting all SZL Holdings domain packs.


[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red?style=flat-square)](../../LICENSE.md)

[Live Demo](https://szlholdings.com) · [Platform Demo Video](https://szlholdings.com/szl-demo-video/) · [Investor Dashboard](https://szlholdings.com/stephen/investor) · [Architecture](../../docs/architecture/architecture.md)

![A11oy — Brand Orchestration Layer](../../.github/assets/screenshots/a11oy-hero.jpg)

---

## What it does

**ROADMAP product contract** — this legacy SPA is intended to provide an Alloy
Fabric view of agent status, decisions, policy gates, and proof-chain
attributions. The current repository does not prove that every estate action
routes through this surface.

**EXISTS (source-level)** — source for those views is present under `web/`;
this is a code-presence claim, and clean-clone workspace wiring remains
incomplete as disclosed below.

## Build status

**ROADMAP** — this legacy SPA is present under `web/`, but the repository root
workspace does not currently include it and several `workspace:*` dependencies
are unresolved. The commands below describe the intended monorepo workflow;
they are not a clean-clone quickstart until `pnpm -r build` proves the wiring.

## Intended local workflow

```bash
# Intended workflow after the workspace is fully wired
pnpm install
pnpm --filter @workspace/api-server dev   # Start the API server first
pnpm --filter @workspace/a11oy dev
```

**ROADMAP route:** `/a11oy/`

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
