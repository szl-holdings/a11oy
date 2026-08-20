# ouroboros/category

**Operationalizes:** TH4 — Λ-Category (receipt morphisms)  
**Repo:** szl-holdings/ouroboros  
**Path:** packages/category

## What it does

Models the collection of valid receipts as a **category** where:

- **Objects** are receipt hashes
- **Morphisms** are typed, directed edges between hashes with a stable `id`
- **Identity** morphisms satisfy `id.domain == id.codomain`
- **Composition** is defined by `composeMorphisms(f, g)` with a runtime boundary check

Functor laws (identity + composition) are asserted as runtime invariants via `assertFunctorLaws`.

## Exports

| Symbol | Purpose |
|--------|---------|
| `morphism(domain, codomain, label)` | Create a morphism |
| `identityMorphism(receipt)` | Identity morphism for a receipt |
| `composeMorphisms(f, g)` | Compose f then g; returns `ComposeResult` |
| `assertFunctorLaws(F, receipt, f, g)` | Assert functor identity + composition laws |
| `validateMorphismEndpoint(r)` | Gate-check receipt at morphism endpoint |

## Env vars

None.

## HTTP endpoints

None — library only.

## Install & test

```bash
pnpm install
pnpm test
```
