# amaru — provenance anchor

<div class="quechua">
<strong>Etymology.</strong> Quechua <strong><em>amaru</em></strong> = <strong>serpent</strong>
(the Andean serpent of rivers and continuity). The metaphor is the unbroken chain: amaru
threads governance receipts into a single, continuous, anchored line. Gloss:
<a href="https://kaikki.org/eswiktionary/">kaikki.org Quechua lexicon</a>.
</div>

## Overview

`amaru` handles **blockchain anchoring of governance receipts** with **Shor-encoded
provenance**: provenance hashes are encoded with the 9-qubit Shor code before Cardano
anchoring, giving single-qubit error correction on the immutable receipt chain. It performs
convergent multi-source data sync with append-only delta logs and bounded-loop convergence
guarantees.

> **Frontier capability.** First Shor-encoded + Cardano-anchored governance-receipt minting
> pipeline.

**Anatomy mapping:** amaru sits across [Yawar](/anatomy/#yawar) (the receipt ledger) and
the [Khipu](/anatomy/#khipu) DAG, providing the durable external anchor.

## Mathematical foundation

| Property | Guarantee | Source |
|----------|-----------|--------|
| **Convergence** | The delta-log compression operator is a **contraction mapping** on hash-verified ingest sequences under the ℓ∞ norm | [Banach, 1922](https://doi.org/10.4064/fm-3-1-133-181) |
| **Error correction** | Provenance hashes are **Shor 9-qubit** encoded for single-qubit correction on the anchor chain | [Shor, 1995](https://doi.org/10.1103/PhysRevA.52.R2493) |
| **Causal order** | Receipt events carry **Lamport timestamps** for total causal order across nodes | [Lamport, 1978](https://doi.org/10.1145/359545.359563) |

Banach contraction (the convergence guarantee): there exists $q \in [0,1)$ such that for the
compression operator $T$,

$$ d\big(T(x), T(y)\big) \le q \cdot d(x, y), $$

so iterating $T$ converges to a unique fixed point — the canonical synced ledger state.

## API / install

```sh
git clone https://github.com/szl-holdings/amaru.git
cd amaru
pnpm install
pnpm test
```

## Example — mint a receipt

```ts
import { mintReceipt } from '@szl/amaru'

const receipt = mintReceipt({
  payload: { decisionId: 'd-001', value: 1, organ: 'a11oy.policy' },
})

console.log(receipt.sha256)   // SHA-256 over the canonical JSON
console.log(receipt.lamport)  // Lamport timestamp for causal order
console.log(receipt.shorBlock)// Shor-9 encoded provenance block
```

::: warning In development
**Cardano mainnet anchoring** is in development (target: Series-A milestone). The local
append-only delta log, Shor encoding, and Lamport ordering are **live today** and tested
via `pnpm test`. The DSSE receipt **signature** field is a PLACEHOLDER until Sigstore CI
lands (see [Compliance](/compliance)).
:::

## Source & evidence

- **Repo:** [github.com/szl-holdings/amaru](https://github.com/szl-holdings/amaru)
- **Spec:** [ouroboros-thesis](https://github.com/szl-holdings/ouroboros-thesis)
- **Proofs:** [`lutar-lean`](https://github.com/szl-holdings/lutar-lean)
- **DOI (versioned):** [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) · **Concept DOI:** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)
- **License:** Apache-2.0
