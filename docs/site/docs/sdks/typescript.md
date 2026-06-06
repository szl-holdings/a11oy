# szl-ts

The TypeScript client for the SZL anatomy.

::: warning In development
`szl-ts` is **in development** (target: Series-A milestone). The interface below is the
**planned** unified surface. The per-flagship packages it wraps —
`@szl-holdings/a11oy-policy`, `@szl-holdings/a11oy-measurement`, `@szl/amaru`, rosie's
`khipu-receipt` — are **live today** and are the supported interim path (see the
[Quickstart](/quickstart)).
:::

## Install (planned)

```bash
npm install @szl-holdings/szl   # in development — not yet published
# or
pnpm add @szl-holdings/szl
```

## Init (planned)

```ts
import { Client } from '@szl-holdings/szl'

const szl = new Client({ org: 'szl-holdings' }) // honest local mode; signing not yet wired
```

## Examples (planned surface)

```ts
// 1 · 13-axis Λ-gate (a11oy)
const decision = szl.policy.evaluate({
  action: 'deploy-model',
  axes: { moralGrounding: 0.97, measurabilityHonesty: 0.96 /* ...13 axes */ },
})

// 2 · Khipu receipt DAG + sum invariant (rosie)
const root = szl.receipts.root(organReceipts)
szl.receipts.verifySumInvariant(root)      // rootValue = Σ Σ decisionValues
szl.receipts.verifyDualAttestation(root)   // two distinct signers

// 3 · Posture-drift score (sentra)
const report = szl.sentra.driftScore({ baseline, observed })
```

## Interim path (live today)

```bash
npm install @szl-holdings/a11oy-policy @szl-holdings/a11oy-measurement
# rosie / amaru / sentra: clone the repo and `pnpm install && pnpm test`
```
