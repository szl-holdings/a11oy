# Provenance Anchor

> **Naming note.** This component was previously tracked under the internal codename
> *amaru* (Quechua for *serpent* — the Andean serpent of rivers and continuity, evoking the
> unbroken receipt chain). The honest, user-facing name is **Provenance Anchor**; the codename
> is retired and retained here only as historical context.

## Overview

The **Provenance Anchor** handles **blockchain anchoring of governance receipts** with
**Shor-encoded provenance**: provenance hashes are encoded with the 9-qubit Shor code before
Cardano anchoring, giving single-qubit error correction on the immutable receipt chain. It
performs convergent multi-source data sync with append-only delta logs and bounded-loop
convergence guarantees.

> **Frontier capability (roadmap).** A Shor-encoded + Cardano-anchored governance-receipt
> minting pipeline. Cardano mainnet anchoring is roadmap (see the development note below).

**Anatomy mapping:** the Provenance Anchor sits across [Yawar](/anatomy/#yawar) (the receipt
ledger) and the [Khipu](/anatomy/#khipu) DAG, providing the durable external anchor.

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

## Example — mint a receipt

```ts
import { mintReceipt } from '@szl/provenance-anchor'

const receipt = mintReceipt({
  payload: { decisionId: 'd-001', value: 1, organ: 'a11oy.policy' },
})

console.log(receipt.sha256)   // SHA-256 over the canonical JSON
console.log(receipt.lamport)  // Lamport timestamp for causal order
console.log(receipt.shorBlock)// Shor-9 encoded provenance block
```

::: warning In development
**Cardano mainnet anchoring** is roadmap (target: Series-A milestone). The local
append-only delta log, Shor encoding, and Lamport ordering are **live today** and tested.
The DSSE receipt **signature** field is a PLACEHOLDER until Sigstore CI lands (see
[Compliance](/compliance)).
:::

## Source & evidence

- **Spec:** ouroboros-thesis
- **Proofs:** [`lutar-lean`](https://github.com/szl-holdings/lutar-lean)
- **DOI (versioned):** [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) · **Concept DOI:** [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)
- **License:** Apache-2.0
