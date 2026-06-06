# ouroboros/closure

**Operationalizes:** TH3 — ρ-Closure Composition  
**Repo:** szl-holdings/ouroboros  
**Path:** packages/closure

## What it does

Implements the ρ-closure operation: chaining N individually-valid receipts into a single composite receipt. The composition uses **component-wise minimum** on all 9 axes, giving the composite a Λ-score bounded by the weakest link in the chain.

Key algebraic properties guaranteed by the implementation:

| Property | Guarantee |
|----------|-----------|
| Associativity | `compose([a,b,c]) == compose([compose([a,b]), c])` |
| Identity | `composeAxes(r, IDENTITY_AXES) == r` |
| Commutativity | `composeAxes(a,b) == composeAxes(b,a)` |
| Determinism | Composite hash is SHA-256 of sorted source hashes |

## Exports

| Symbol | Purpose |
|--------|---------|
| `compose(receipts)` | Chain N receipts → `CompositionResult` |
| `composeAxes(a, b)` | Component-wise minimum of two axis sets |
| `IDENTITY_AXES` | Neutral element (all 1.0) |
| `checkAssociativity(a,b,c)` | Property-test helper |

## Env vars

None.

## HTTP endpoints

None — library only. Use in combination with `lambda-gate` server.

## Install & test

```bash
pnpm install
pnpm test
```
