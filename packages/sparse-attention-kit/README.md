# @szl-holdings/sparse-attention-kit

Typed sparse-attention envelope + receipt layer. **No CUDA kernel ships here.**

Re-expressed from the 2025 sparse-attention wave (MiniMax M1/M2, DeepSeek NSA, Moonshot MoBA, Tri Dao FlashAttention, Songlin Yang FLA) against Doctrine V6. The non-negotiable design decision is documented in `docs/research/sparse-attention-synthesis-2026.md`:

> MiniMax M2 *reverted* to full attention after hybrid-sparse matched full attention on small benchmarks but **degraded measurably on multi-hop reasoning at scale.** The lesson is not "sparse is the answer" — it is **"sparse without a contradiction detector and an escalation path is a benchmark trick that fails industrial validation."**

So this kit ships five primitives and twelve `sparse.*.v1` receipt classes that make that lesson structural rather than folk:

| Primitive | Source | Doctrine V6 receipts |
| --- | --- | --- |
| `envelope`           | MiniMax M2 "no-free-lunch"     | `sparse.regime.admitted.v1`, `sparse.regime.rejected.v1`, `sparse.regime.demoted.v1` |
| `contradiction-probe`| MiniMax M2 + ROSIE             | `sparse.contradiction.v1`, `sparse.escalated.v1` |
| `two-level-commit`   | DeepSeek NSA                   | `sparse.index.score.v1`, `sparse.topk.commit.v1`, `sparse.execute.v1`, `sparse.budget.exhausted.v1` |
| `recorded-router`    | Moonshot MoBA                  | `sparse.router.trace.v1` |
| `io-budget`          | FlashAttention (Tri Dao)       | `sparse.io.budget.v1`, `sparse.io.overrun.v1` |

## Usage

```ts
import {
  admit, probe, scoreIndex, topKCommit, executeSparse,
  recordedRouter, recordIo,
} from "@szl-holdings/sparse-attention-kit";
```

Every function is **pure** — no transport, no logger, no side effect. The caller writes the returned receipt to the ledger; the api-server owns the persist/emit transport.

## Doctrine contract

- A sparse plan that lacks `sparse.regime.admitted.v1` MUST NOT execute.
- A sparse step that lacks a fresh `sparse.topk.commit.v1` parent MUST NOT execute (`sparse.execute.v1` is rejected at receipt-write).
- A `sparse.contradiction.v1` without a paired `sparse.escalated.v1` is a doctrine violation.
- A `sparse.router.trace.v1` whose `blocksSelected.length > envelope.maxBlocks` MUST trigger router demotion (NOT silent truncation).
- A `sparse.io.overrun.v1` with `overrunRatio > 1` is a Sentra fail-closed event for the next admission attempt from that tenant.
