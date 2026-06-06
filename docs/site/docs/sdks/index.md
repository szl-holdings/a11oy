# SDKs

SZL is shipping two first-party client SDKs that wrap the [flagships](/flagships/) and the
[anatomy](/anatomy/) organs behind a single typed surface: **`szl-python`** for Python and
**`szl-ts`** for TypeScript.

::: warning In development
The unified `szl-python` and `szl-ts` packages are **in development**. Today, each flagship is
consumed via its own package (`@szl-holdings/a11oy-policy`, `@szl/amaru`, etc.) or its live
Space API (killinchu). The unified SDKs roll those into one client with shared receipt,
Λ-gate, and Khipu types.

**Target:** first public `szl-python` + `szl-ts` release at the Series-A milestone. Until then,
the per-flagship packages on [the org](https://github.com/szl-holdings) and the
[Quickstart](/quickstart) are the supported path.
:::

## What the SDKs unify

| Capability | Backed by | Status |
|------------|-----------|--------|
| Policy evaluation (13-axis Λ-gate) | [a11oy](/flagships/a11oy) | per-package live; unified in dev |
| Receipt minting + anchoring | [amaru](/flagships/amaru) | local live; Cardano mainnet in dev |
| Khipu receipt DAG + sum invariant | [rosie](/flagships/rosie) | live |
| Posture-drift scoring | [sentra](/flagships/sentra) | live |
| Counter-UAS / protocol decode | [killinchu](/flagships/killinchu) | live (Space API) |

## Design principles

- **One receipt type.** Every call returns a Khipu receipt with the canonical
  `sha256 / prevRoot / lamport / signature` shape (signature `DSSE-PLACEHOLDER` until signing
  lands).
- **Honest errors.** Malformed input returns an explicit error — never a silent pass.
- **Doctrine-typed.** The 13 Yuyay axes and 10 HUKLLA tripwires are first-class enums.

See [`szl-python`](/sdks/python) and [`szl-ts`](/sdks/typescript) for the planned surface and
the per-flagship interim path.
