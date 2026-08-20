# ouroboros/types

**Operationalizes:** TH7 — Typed Receipts as Propositions  
**Repo:** szl-holdings/ouroboros  
**Path:** packages/types

## What it does

Defines the canonical `Receipt` type and its Zod schema. Every downstream module imports from here. The key thesis mapping is:

> A receipt is a typed proof-object (proposition) asserting `Λ(h) ≥ 0.90` for hash `h`. Malformed receipts are rejected at parse time — there is no runtime duck-typing.

### Exports

| Symbol | Purpose |
|--------|---------|
| `ReceiptSchema` | Zod schema for full receipt validation |
| `AxesSchema` | Zod schema for the 9-axis score vector |
| `parseReceipt(raw)` | Parse & throw on invalid |
| `safeParseReceipt(raw)` | Parse & return `{success, data}` |
| `receiptToProposition(r)` | Map receipt → `Proposition` |
| `Receipt`, `Axes`, `Proposition` | TypeScript types |

## Env vars

None — pure library module.

## HTTP endpoints

None — library only.

## Usage

```ts
import { parseReceipt } from "@szl/ouroboros-types";

const receipt = parseReceipt(rawJson); // throws ZodError if malformed
```

## Install & test

```bash
pnpm install
pnpm test
```
