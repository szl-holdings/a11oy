# Iron-Dome-but-the-brain

A precise framing of where SZL sits in a layered-defense picture: **the brain, not the missile.**
SZL builds the *governed decision layer* — the part that decides, under proof, what a
recommendation *is* — and explicitly does **not** build effectors.

## The distinction

An interceptor system has two halves: a **decision** half (detect, classify, prioritise, decide
whether and how to respond) and an **effector** half (the kinetic action). SZL is entirely in the
decision half, and only the *governed* part of it:

| Layer | Who owns it | SZL? |
|-------|-------------|------|
| Sensing / detection | sensors, radar, broadcast feeds | partial — [killinchu](/flagships/killinchu) decodes broadcast self-ID |
| Classification / track | tracking systems | partial — killinchu track + swarm topology |
| **Governed decision** | **the brain** | **yes — this is SZL** |
| Effector / engagement | weapons systems | **no — out of scope by design** |

## What "the brain" actually does

1. **Bounds the action space** — the [Bekenstein / geofence](/doctrine/puriq) invariant (INV-4)
   makes the set of considered actions finite and physically feasible (the
   [Killinchu-bridge `G(a)`](/anatomy/#killinchu-bridge) factor).
2. **Gates every candidate** — the [13-axis Λ-gate](/doctrine/v11-v12) admits a recommendation
   only if all 13 axes clear their floors (conjunctive AND).
3. **Halts safely** — the [HUKLLA soft-halt](/anatomy/#hukulla) drives utility to zero on any
   fired tripwire; T10 (STOP) is absorbing (INV-1).
4. **Receipts everything** — every decision emits a [Khipu receipt](/anatomy/#khipu), so the
   *why* is replayable (INV-3).

The output is an **auditable recommendation with a proof chain** — not a fire command.

## Why this framing matters

It is the honest, defensible scope. SZL's value is that a human reviewer can replay the brain's
reasoning with cosign and Lean and see exactly which axis admitted or rejected an action. That is
the [Warhacker thesis](/use-cases/warhacker) applied to a kinetic domain: **delivery +
verification + governance, never the weapon.**

::: warning Doctrine v11 scope discipline
**No autonomous lethal action.** A human remains in the loop for any kinetic outcome. SZL produces
the governed decision and its receipt; it does not actuate.
:::
