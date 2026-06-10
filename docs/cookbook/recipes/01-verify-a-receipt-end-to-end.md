# Verify a receipt end-to-end

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

> **Pull a real Khipu receipt from `szl-lake`, validate its ECDSA-P256 DSSE signature against the org cosign key, then re-check it through `a11oy /v1/verify` and read the doctrine posture from `sentra`.**
>
> **Headline number: 1 receipt → 1 cryptographic VALID in < 60 seconds, zero credentials.**

This is the canonical first-touch recipe. It is the most important thing the cookbook does:
it proves, on your own machine, that an SZL governance receipt is what it claims to be.

The signature checked here is **real** — not a placeholder. The amaru tick receipt in the live
[`szl-lake`](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake) dataset is signed with the
organization cosign key published at
[`.github/cosign.pub`](https://github.com/szl-holdings/.github/blob/main/cosign.pub),
and this recipe verifies it against that key with no founder credentials required.

> **Honest scope.** The *live HF Spaces* still emit receipts whose `dsse_sig` is the string
> `PLACEHOLDER` (Sigstore CI signing is pending per Doctrine v11). The *lake* NDJSON receipt
> used below carries a genuine ECDSA-P256 signature that validates. Use the lake receipt for a
> true end-to-end proof; use the live Space tick to see the receipt *shape*.

---

## Prerequisites

```bash
python3 -m pip install cryptography requests
# curl + jq for the optional live-Space steps
```

No API key, no GHCR token, no founder credentials needed for the core verification.

---

## Quickstart (the headline number)

```python
import base64, json, urllib.request
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives import hashes, serialization

LAKE = "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main"

# 1. Pull one real receipt from the lake (canonical HF mirror).
line = urllib.request.urlopen(f"{LAKE}/khipu/amaru_receipts.ndjson", timeout=30).readline()
r = json.loads(line)

# 2. Fetch the org verify key the receipt points to.
key_pem = urllib.request.urlopen(
    "https://raw.githubusercontent.com/szl-holdings/.github/main/cosign.pub", timeout=30
).read()
pub = serialization.load_pem_public_key(key_pem)

# 3. Verify: ECDSA-P256 over the raw SHA-256 of the DSSE PAE (prehashed).
sig    = base64.b64decode(r["dsse_sig"])
digest = bytes.fromhex(r["dsse_pae_sha256"])
pub.verify(sig, digest, ec.ECDSA(Prehashed(hashes.SHA256())))   # raises if invalid
print("VALID:", r["receipt_id"][:16], "signed by", r["dsse_keyid"])
# => VALID: 4c9c3f2b8d6452d9 signed by szlholdings-cosign
```

If `pub.verify` returns without raising, the receipt is authentic. Tamper with one byte of the
payload or the signature and it raises `InvalidSignature` — that is the whole point.

---

## Full walkthrough

### Step 1 — Understand the receipt shape

A lake Khipu receipt is one NDJSON line. The signature-relevant fields are:

| Field | Meaning |
|---|---|
| `receipt_id` | SHA-256 of the receipt body — also the `actual_hash`. |
| `lutar_anchor` | Doctrine kernel commit (`c7c0ba17`) the receipt is pinned to. |
| `lambda`, `lambda_pass` | The Λ score and gate result at emission time. |
| `dsse_payload_type` | `application/vnd.szl.khipu+json`. |
| `dsse_pae_sha256` | SHA-256 of the DSSE Pre-Authentication Encoding — what the signature covers. |
| `dsse_sig` | base64 ECDSA-P256 signature. |
| `dsse_keyid` | `szlholdings-cosign`. |
| `verify_key_url` | Points at `.github/cosign.pub` — the key above. |

DSSE (Dead Simple Signing Envelope, [in-toto/ITE-5](https://github.com/secure-systems-lab/dsse))
binds the signature to the payload **type** as well as the bytes, via the PAE:

```
PAE = "DSSEv1 " ‖ len(type) ‖ " " ‖ type ‖ " " ‖ len(body) ‖ " " ‖ body
```

The SZL signer signs `SHA-256(PAE)`, so verification is a prehashed ECDSA check — exactly what the
quickstart does.

### Step 2 — Verify the doctrine anchor matches the locked kernel

A receipt is only meaningful if its doctrine anchor is the locked one. Cross-check against the
lake index:

```python
idx = json.loads(urllib.request.urlopen(f"{LAKE}/lake_index.json", timeout=30).read())
assert r["lutar_anchor"] == idx["kernel_commit"] == "c7c0ba17", "doctrine drift!"
assert (idx["declarations"], idx["axioms"], idx["sorries"]) == (749, 14, 163)
print("doctrine OK:", idx["kernel_commit"], idx["declarations"], idx["axioms"], idx["sorries"])
# => doctrine OK: c7c0ba17 749 14 163
```

### Step 3 — Tamper test (prove the check has teeth)

```python
bad = bytearray(sig); bad[10] ^= 0x01            # flip one bit of the signature
try:
    pub.verify(bytes(bad), digest, ec.ECDSA(Prehashed(hashes.SHA256())))
    print("UNEXPECTED: tampered sig accepted")
except Exception:
    print("REJECTED tampered signature — as designed")
```

### Step 4 (optional, live) — Round-trip through `a11oy /v1/verify`

When the a11oy Space is warm, re-check a chain through the substrate:

```bash
curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest | jq .kernel_commit
# => "c7c0ba17"   (authoritative live doctrine probe)

curl -s -X POST https://szlholdings-a11oy.hf.space/api/a11oy/v1/verify \
  -H 'content-type: application/json' \
  -d "$(python3 -c 'import json,urllib.request;L="https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main";print(urllib.request.urlopen(L+"/khipu/amaru_receipts.ndjson").readline().decode())')" \
  | jq .
```

> **Honest note.** The a11oy / sentra Spaces sleep on Hugging Face's free tier and may return
> "Space is in error" until warmed — open the Space URL once to wake it. The lake-based
> verification in Steps 1–3 needs no Space at all.

### Step 5 (optional, live) — Read the verdict posture from `sentra`

```bash
curl -s https://szlholdings-sentra.hf.space/api/sentra/v1/honest | jq '{doctrine, slsa}'
# => { "doctrine": "v11", "slsa": "L1 (honest)" }
```

---

## What you proved

1. A receipt drawn from the public lake is **cryptographically authentic** under the org key.
2. Its doctrine anchor equals the **locked** kernel (`c7c0ba17`, 749/14/163).
3. Any tampering is rejected.

That is the SZL invariant `receipts.in ≡ receipts.out`, made concrete.

---

## See also

- **[02 — Deploy the 5-flagship UDS bundle](02-deploy-5-flagship-uds-bundle.md)** — run the organs that emit these receipts.
- **[06 — Verify cosign + Rekor for SLSA L1](06-cosign-rekor-slsa-l1.md)** — verify the *container* that runs the organ.
- **[08 — Receipt knot algebra](08-receipt-knot-algebra.md)** — the topology of receipt chains.
- **[12 — Doctrine ledger query](12-doctrine-ledger-query.md)** — programmatic access to 749/14/163.
- Live: [amaru](https://szlholdings-amaru.hf.space) · [a11oy](https://szlholdings-a11oy.hf.space) · [sentra](https://szlholdings-sentra.hf.space)

## Cite this recipe

```bibtex
@misc{szl_cookbook_verify_receipt_2026,
  title        = {Verify a receipt end-to-end (SZL Cookbook recipe 01)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/01-verify-a-receipt-end-to-end.md}},
  note         = {Doctrine v11 LOCKED 749/14/163, kernel c7c0ba17. DOI 10.5281/zenodo.20434308}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
