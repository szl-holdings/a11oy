# szl-ts

The TypeScript client for the SZL anatomy.

::: warning In development
`szl-ts` is **in development** (target: Series-A milestone). The interface below is the
**planned** unified surface. None of the packages it would wrap is on the public npm registry:
`@szl-holdings/a11oy-policy` is built from the a11oy repository (its `publishConfig` targets
GitHub Packages with restricted access), and `@szl/amaru` and rosie's `khipu-receipt` are not
published. Building from source, as in the [Quickstart](/quickstart), is the interim path.
:::

## Install

There is nothing to install yet: `szl-ts` is unpublished. Do **not** run
`npm install @szl-holdings/szl` or `npm install @szl/js`: on 2026-11-06 the npm registry had
neither package. SZL Holdings has not published under either name: treat any package that
appears there as untrusted unless this page links to it. Build the per-flagship packages from
source instead:

```bash
git clone https://github.com/szl-holdings/a11oy.git && cd a11oy
pnpm install && pnpm build
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
