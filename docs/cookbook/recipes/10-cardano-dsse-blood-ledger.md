# Cardano-anchored DSSE blood ledger

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

> **Batch a set of DSSE Khipu receipts into a Merkle root and anchor that root as Cardano transaction metadata — a public, immutable timestamp for your governance "blood ledger."**
>
> **Headline number: N receipts → 1 Merkle root → 1 on-chain metadatum.**

amaru calls its receipt chain the *yawar* (blood) ledger. Anchoring its Merkle root on Cardano L1
gives an independent, public proof-of-existence. This is **hash anchoring only** — not a token,
not custodial, not a transfer of value.

> **HONEST PREREQUISITE — READ FIRST.** amaru's live `/v1/honest` states:
> *"Cardano-anchored receipts are demo-seeded, not on-chain mainnet."* Mainnet (and even funded
> testnet) submission requires **founder credentials** (a funded wallet + signing keys). This
> recipe therefore has two paths:
> 1. **Demo path (no credentials)** — build and verify the Merkle root + the metadata payload
>    locally. Fully runnable here.
> 2. **Testnet path (requires a funded Cardano preprod wallet)** — submit the root and retrieve the
>    proof. Clearly gated below.

---

## Prerequisites

```bash
python3 -m pip install requests          # demo path
# Testnet path additionally needs: cardano-cli OR a Blockfrost preprod project_id,
# and a funded preprod wallet. These are FOUNDER-PROVIDED credentials.
```

---

## Quickstart — demo path (no credentials)

```python
import hashlib, json, urllib.request

LAKE = "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main"
lines = urllib.request.urlopen(f"{LAKE}/khipu/amaru_receipts.ndjson", timeout=30).read().splitlines()
leaves = [hashlib.sha256(l).digest() for l in lines if l.strip()]

def merkle_root(leaves):
    if not leaves: return b"\x00" * 32
    layer = leaves
    while len(layer) > 1:
        if len(layer) % 2: layer = layer + [layer[-1]]            # duplicate last
        layer = [hashlib.sha256(layer[i] + layer[i+1]).digest() for i in range(0, len(layer), 2)]
    return layer[0]

root = merkle_root(leaves).hex()
metadatum = {"674": {"msg": ["szl.khipu.anchor/v1", f"root:{root}",
                              "doctrine:v11", "kernel:c7c0ba17"]}}   # CIP-20 label 674
print("merkle_root:", root)
print("cardano_metadatum:", json.dumps(metadatum))
```

The `674` label is the [CIP-20](https://cips.cardano.org/cip/CIP-20) transaction-message standard —
the conventional home for arbitrary anchor strings.

---

## Full walkthrough

### Step 1 — Verify the receipts before you anchor

Anchoring a forged receipt just timestamps a forgery. Verify each receipt's signature first
(**[recipe 01](01-verify-a-receipt-end-to-end.md)**) so the Merkle root commits to *authentic*
receipts only.

### Step 2 — Build a stable, ordered Merkle tree

Sort receipts by `(seq, receipt_id)` so the root is deterministic and reproducible by an auditor.
Record the leaf order alongside the root.

### Step 3 — Form the metadata payload

Keep each metadata string ≤ 64 bytes (Cardano metadata constraint). Split the root across two
strings if needed, or store `root` plus a pointer to the leaf-order file in the lake.

### Step 4 (gated) — Submit to Cardano preprod testnet

> Requires a funded preprod wallet — **founder credentials**.

```bash
# Example with cardano-cli (preprod). Wallet keys are founder-supplied; never commit them.
cardano-cli transaction build \
  --testnet-magic 1 \
  --tx-in "$UTXO" --change-address "$ADDR" \
  --metadata-json-file metadatum.json \
  --out-file tx.raw
cardano-cli transaction sign --tx-body-file tx.raw --signing-key-file payment.skey \
  --testnet-magic 1 --out-file tx.signed
cardano-cli transaction submit --tx-file tx.signed --testnet-magic 1
```

### Step 5 — Retrieve the proof

After confirmation, the transaction hash *is* the proof. Resolve it on a preprod explorer or via
Blockfrost:

```bash
curl -s -H "project_id: $BLOCKFROST_PREPROD" \
  "https://cardano-preprod.blockfrost.io/api/v0/txs/$TXHASH/metadata" | jq .
```

Store `{merkle_root, leaf_order_url, tx_hash, network: "preprod"}` back in the lake as the anchor
receipt — itself verifiable by recipe 01.

---

## See also

- **[01 — Verify a receipt end-to-end](01-verify-a-receipt-end-to-end.md)** — verify before anchoring.
- **[05 — Memory-attested reasoning](05-memory-attested-reasoning.md)** — the chain you're anchoring.
- Live: [amaru](https://szlholdings-amaru.hf.space) · [CIP-20](https://cips.cardano.org/cip/CIP-20)

## Cite this recipe

```bibtex
@misc{szl_cookbook_cardano_anchor_2026,
  title        = {Cardano-anchored DSSE blood ledger (SZL Cookbook recipe 10)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/10-cardano-dsse-blood-ledger.md}},
  note         = {Hash anchoring only; mainnet/testnet submission needs founder credentials. Demo path needs none.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
