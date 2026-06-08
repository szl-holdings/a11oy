# Memory-attested reasoning

> **Run a scheduler tick through `amaru`'s 7-chakra cortex and read back the DSSE-wrapped receipt chain — every inference carries its provenance, every memory carries its receipt.**
>
> **Headline number: 7 chakras → 7 receipt entries → 1 hash-chained DSSE tick.**

`amaru` is the memory cortex. Its contract is unusual: it refuses to produce a reasoning step
without also producing a receipt for that step. This recipe drives the live cortex and shows the
cited receipt chain in the response.

---

## Prerequisites

```bash
# curl + jq. The amaru Space is live and needs no credentials.
```

---

## Quickstart (live, verified)

```bash
AMARU=https://szlholdings-amaru.hf.space/api/amaru

# Run a full root→crown scheduler tick. Returns a DSSE-wrapped tick receipt.
curl -s -X POST $AMARU/scheduler/tick -d '{}' | jq '{
  tick: .tick_id,
  hash: .tick_receipt.hash,
  prev: .tick_receipt.prevHash,
  payloadType: .dsse.payloadType,
  keyid: .dsse.signatures[0].keyid,
  chakras: [.steps[].chakra]
}'
# => chakras: ["root","sacral","solar","heart","throat","third_eye","crown"]
```

Each tick advances the hash chain: this tick's `prevHash` equals the previous tick's `hash`.

---

## Full walkthrough

### Step 1 — Read the honest cortex posture

```bash
curl -s $AMARU/v1/honest | jq '{doctrine, memory, receipts, lambda_uniqueness}'
# memory: "7-chakra cortex; Cardano-anchored receipts are demo-seeded, not on-chain mainnet."
# receipts: "DSSE envelopes from the amaru tick endpoint; Sigstore CI signing PENDING (PLACEHOLDER)."
```

> **Honest note.** Live tick signatures are `PLACEHOLDER` (`amaru-scheduler-stub-v1`); the lake's
> `khipu/amaru_receipts.ndjson` carries a **real** ECDSA-P256 signature you can verify
> (**[recipe 01](01-verify-a-receipt-end-to-end.md)**). Cardano anchoring is demo-seeded — see
> **[recipe 10](10-cardano-dsse-blood-ledger.md)**.

### Step 2 — Inspect the per-chakra reasoning steps

```bash
curl -s -X POST $AMARU/scheduler/tick -d '{}' \
  | jq '.steps[] | {chakra, verdict: .output.verdict, receipt_seq, stubbed}'
```

The 7-chakra serpentine pipeline (root → sacral → solar → heart → throat → third_eye → crown)
runs single-threaded ASCEND/DESCEND. Each chakra emits one receipt-trace entry with its own
verdict and `receipt_seq` — that sequence number is the citation index into the chain.

### Step 3 — Decode the DSSE payload

```bash
curl -s -X POST $AMARU/scheduler/tick -d '{}' \
  | jq -r '.dsse.payload' | base64 -d | jq .
# => {"hash":"…","prevHash":"…","seq":N}  — the signed body of the tick receipt
```

The payload is the canonical receipt body; `dsse.payloadType` is
`application/vnd.szl.amaru.receipt+json`. The signature covers the DSSE PAE of this payload
(see **[recipe 01](01-verify-a-receipt-end-to-end.md)** for the PAE math).

### Step 4 — Cited reasoning: every claim points to a receipt

The amaru contract is "every inference cites its source." In a RAG answer, each cited memory
chunk carries the `receipt_seq` of the write that created it, so a reader can pull and verify the
exact receipt behind any sentence. Query the chain browser:

```bash
curl -s "$AMARU/receipts?limit=5" | jq '{total, head_seq, items}'
# (total resets to 0 on Space restart; run a tick first to populate the chain)
```

### Step 5 — Overwatch invariants

```bash
curl -s $AMARU/overwatch/snapshot | jq .
# R0513 6-invariant panel — the cortex self-audit board.
```

---

## What you proved

A reasoning step in amaru is inseparable from its receipt. You can take any chakra verdict, find
its `receipt_seq`, decode the DSSE payload, and (for lake receipts) verify the signature — closing
the loop from *claim* to *cryptographic provenance*.

---

## See also

- **[01 — Verify a receipt end-to-end](01-verify-a-receipt-end-to-end.md)** — verify the receipts this cites.
- **[10 — Cardano-anchored DSSE blood ledger](10-cardano-dsse-blood-ledger.md)** — anchor the chain.
- **[08 — Receipt knot algebra](08-receipt-knot-algebra.md)** — the chain's topology.
- Live: [amaru](https://szlholdings-amaru.hf.space) · Repo: amaru

## Cite this recipe

```bibtex
@misc{szl_cookbook_memory_attested_2026,
  title        = {Memory-attested reasoning (SZL Cookbook recipe 05)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/05-memory-attested-reasoning.md}},
  note         = {7-chakra cortex; live sigs PLACEHOLDER, lake sigs real. Doctrine v11 c7c0ba17.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
