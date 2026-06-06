# ouroboros/glr

**Operationalizes:** TH8 — Graded Linear Receipts  
**Repo:** szl-holdings/ouroboros  
**Path:** packages/glr

## What it does

Implements a **linear type system** for receipts. In linear logic, every resource must be used **exactly once** — this module enforces that invariant via a `ConsumptionLedger`.

Each receipt is assigned a **grade** (A/B/C/D) derived from its Λ score. Grades compose by the weakest-link principle.

### Linear Typing Rules

| Rule | Behaviour |
|------|-----------|
| Registration | A receipt must be registered before use |
| Single-consume | `consume(hash)` throws `LinearityError` if called twice |
| Peek | `peek(hash)` inspects without consuming |
| Availability | `listAvailable(minGrade)` returns only unconsumed receipts above a grade threshold |

### Grade Mapping

| Grade | Λ range |
|-------|---------|
| A | ≥ 0.95 |
| B | ≥ 0.92 |
| C | ≥ 0.90 |
| D | < 0.90 |

## Env vars

None.

## HTTP endpoints

None — library only.

## Install & test

```bash
pnpm install
pnpm test
```
