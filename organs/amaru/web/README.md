# Amaru — The Andean Ouroboros

> Convergent multi-source data synchronization with Proof-Chain receipts — the SZL Holdings reference implementation of the Ouroboros loop primitive applied to data merge / data sync.

[![Status: Series-A](https://img.shields.io/badge/status-Series--A-brightgreen)](https://github.com/szl-holdings)
[![Built on Ouroboros](https://img.shields.io/badge/runtime-Ouroboros%20v1-purple)](https://github.com/szl-holdings/ouroboros)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue)](https://www.typescriptlang.org/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)

Amaru — named for the Andean ouroboros — is the data-synchronization surface in the SZL Holdings portfolio. It consumes overlapping data streams from heterogeneous sources, runs them through a bounded reconciliation loop with measurable convergence, and emits per-record decision receipts via the Proof Chain.

## Surfaces

| Surface | Purpose |
| --- | --- |
| `/` | Live sync console — current convergence depth, in-flight loops, and per-source priority |
| `/sources` | Source-priority record (one of the proof artifacts required by `PRF_DATA_SYNC`) |
| `/loops` | Trace of every loop run — step-by-step delta, consistency score, and exit reason |
| `/receipts` | Decision-receipt browser — replayable, hash-verified |

## Ouroboros Codex — Amaru's Role

Per Ouroboros Thesis §8 (`docs/research/ouroboros-thesis-v2.md`), Amaru is the **convergent data-sync** archetype. It maps directly to the `PRF_DATA_SYNC` proof route in the v2 runtime contract (`docs/research/ouroboros-runtime-contract.v2.json`), which requires every committed merge to bind:

- a `source_priority_record` (which source won, and why),
- a `delta_log` (what changed step-by-step),
- a `consistency_score` (cross-step agreement, in [0, 1]),
- a `receipt` (the human-readable, replayable decision).

The loop is bounded by `LoopKernel` from `@workspace/ouroboros`, depth-allocated by `EntropyDepthAllocator`, and gated by `evaluateRiskTier` for any record whose merge crosses an R3+ tier (e.g. financial reconciliation, legal-entity unification).

## Architecture

```
                ┌──────────────────────────────────────────────┐
                │           Amaru — Sync Console              │
                ├──────────────────────────────────────────────┤
   Source A ─►  │  ingest → normalize → PRF_DATA_SYNC route   │  ──► merged record
   Source B ─►  │  → LoopKernel(reconcile) → ConsistencyCheck │      + Decision Receipt
   Source C ─►  │  → almanac.advance() → DecisionReceipt      │  ──► Proof Chain ledger
                └──────────────────────────────────────────────┘
                                    │
                                    ▼
                  @workspace/ouroboros · @workspace/codex-kernel
```

## Tech Stack

- React 19 + Vite 7 (artifact: `web`)
- `@workspace/ouroboros` — loop kernel, depth allocator, consistency, proof-route resolver, risk-tier gate, almanac
- `@workspace/codex-kernel` — receipts, validators, replay, trace hash
- TanStack Query 5 + Zustand 5
- Tailwind 4 + shared design system (`@workspace/shared-ui`)

## Source

This README mirrors the artifact at `artifacts/conduit/` inside `szl-holdings/szl-holdings-platform`. The platform monorepo is the source of truth; this repository is a public showcase.

---

© SZL Holdings. Powered by the Ouroboros runtime — see [`szl-holdings/ouroboros`](https://github.com/szl-holdings/ouroboros) and the thesis at `szl-holdings/ouroboros-thesis`.
