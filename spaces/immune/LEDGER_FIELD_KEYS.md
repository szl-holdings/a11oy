# IMMUNE — Frozen Ledger Field-Keys (DECISION)

**Status:** FROZEN · documented 2026-06-18 · do NOT rename, do NOT re-issue genesis
**Scope:** `dist/data/immune/ledger.jsonl`, `dist/data/immune/huklla_evidence.jsonl`, and the
ledger logic inside `dist/immune-server.js`.

## TL;DR

`sentra` survives as an **internal, structural ledger field-key** — *not* as user-visible
prose. It is the immune sentinel's historical codename. It is **intentionally NOT renamed to
`gate`** because the field name is part of the SHA-256 hash-chain input, and renaming it would
invalidate every prior entry's hash and break chain verification. The user-visible name is
**GATE** (served HTML/UI = SENTRA 0 / GATE 3, verified live). This is correct-by-documentation
so no future audit/sentinel false-flags it as a leaked codename.

## Exactly where the field-key lives

1. **`dist/data/immune/ledger.jsonl`** — append-only, SHA-256 hash-chained receipt ledger.
   Each entry's `payload` contains the object key `"sentra"`:
   `payload.sentra = { "accepted": <bool>, "signatureMatched": <string> }` (one per entry, ×5
   over seq 1–5). Each entry's `hash` is computed over the serialized entry **including this
   key**, and `prevHash` links it to the previous `hash` (genesis at seq 1, `prevHash:"GENESIS"`).

2. **`dist/data/immune/huklla_evidence.jsonl`** — the HUKLLA tripwire evidence chain. Tripwire
   **T08** carries the fixed `name` value `"sentra.bypass"` (severity `critical`, ×12, once per
   evidence cycle). This `name` string is part of the per-cycle evidence record.

3. **`dist/immune-server.js`** — the bundled Node/Express immune router. It *reads* the above
   field-key (`payload.sentra`, `sentra.accepted`, `sentra.signatureMatched`, `sentraInspect`,
   `sentraAccepted`) when it serves `/api/immune/ledger/*`, `/api/immune/evidence/*`, and
   `/api/immune/state`, and when it verifies the chain. It does not render `sentra` into any
   page body.

## Why it is NOT user-visible (evidence)

- Served HTML head (`dist/public/index.html`) SEO meta: **GATE** ×3, **SENTRA** ×0 (verified live
  at `https://szlholdings-immune.hf.space/`).
- Frontend SPA bundle (`dist/public/assets/index-*.js`): **sentra = 0** — the React app cannot
  render the literal string `sentra` as body innerText; it labels the admission control "GATE".
- `sentra` appears ONLY in: hash-chained ledger data (JSON field-key / tripwire name) and the
  server bundle that reads those keys. The `/api/immune/*` responses are structural JSON, not
  rendered body innerText.

## Why we do NOT rename (root-cause reasoning, no bandaid)

The ledger is a **verifiable receipt history**. The integrity guarantee is: `hash(entry_n)` is
taken over the entry bytes — which include the `sentra` key — and `entry_{n+1}.prevHash ==
entry_n.hash`. Renaming `sentra` → `gate` would change the hashed bytes of every historical
entry, so:

- every recomputed `hash` would differ from the stored `hash`,
- the chain verifier (`/api/immune/ledger/verify`) would report divergence (tripwire **T06
  `ledger.divergence`** would fire),
- the verifiable receipt history would be destroyed.

The only correct way to rename would be a **deliberate, founder-signed genesis re-issue** that
discards the existing verifiable history — which is **not worth it for a non-user-visible
structural key**. The user-facing surface is already GATE.

## Hard guarantees of this change

- The hash chain was **NOT touched**. No historical entry was rewritten. Genesis was **NOT**
  re-issued. No key/secret was committed.
- This file and any README prose alignment are **additive documentation only**; they do not
  alter `ledger.jsonl`, `huklla_evidence.jsonl`, or the server's chain bytes.

— PRR FINAL immune-ledger sweep, 2026-06-18
