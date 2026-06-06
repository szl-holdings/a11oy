# sentra/confluence

**Operationalizes:** TH5 — Church-Rosser Confluence  
**Repo:** szl-holdings/sentra  
**Path:** packages/confluence

## What it does

Implements the **Church-Rosser (diamond) property** for replay paths. When two derivation branches diverge from a common fork-point and are later independently replayed, `mergeReplayPaths` finds a unique **join receipt** that both paths reduce to — proving the system is confluent (term-rewriting sense).

### Algorithm

1. Check whether the two paths share any common ancestor receipts.
2. If yes — use the last common ancestor's axes as the join basis.
3. If no  — synthesise a join by taking the component-wise minimum of the two terminal receipts' axes.
4. Compute a deterministic join hash from the sorted union of all step hashes.

### Property Tests

| Property | Test |
|----------|------|
| Determinism | Same paths → identical join hash |
| Diamond | Paths sharing a fork are confluent |
| Lambda bound | Join lambda ≥ 0.90 when inputs pass gate |

## Exports

| Symbol | Purpose |
|--------|---------|
| `mergeReplayPaths(pathA, pathB, store)` | Merge two divergent paths |
| `checkDiamondProperty(fork, A, B, store)` | Assert diamond property |

## Env vars

None.

## HTTP endpoints

None — library only.

## Install & test

```bash
pnpm install
pnpm test
```
