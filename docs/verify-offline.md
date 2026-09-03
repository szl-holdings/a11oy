# Verify an SZL receipt chain offline

A stranger's guide to proving an SZL receipt chain is authentic — no SZL
infrastructure, no network calls, no trust in us required. Under 5 minutes.

Every governed state change in the a11oy estate emits a **DSSE envelope**
(`payloadType`, base64 `payload`, `signatures[]`) signed with **ECDSA P-256 /
SHA-256** — the Sigstore cosign default — over the DSSE v1 pre-auth encoding:

```
PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
beat_hash       = sha256(PAE(payloadType, canonical_json(payload)))
```

Each beat's payload carries `prev_beat_hash`, equal to the previous beat's
`beat_hash`. That is the Merkle-style link: flip one byte, reorder, insert, or
delete any beat and at least one of {signature, link, root} breaks.

## Quickstart (fresh clone)

```bash
git clone https://github.com/szl-holdings/a11oy.git && cd a11oy
pip install cryptography          # the only dependency

python examples/verify_chain_offline.py \
    --bundle examples/offline-verify-sample/bundle.json \
    --pubkey examples/offline-verify-sample/pubkey.pem
```

Expected output (root and fingerprint are from the committed sample bundle):

```
[beat   0/3] sig OK · link OK · hash 16b514cc196ff0c8… (keyid matches key fingerprint)
[beat   1/3] sig OK · link OK · hash ea638a24bbaf03df…
[beat   2/3] sig OK · link OK · hash e9c3cb7c3260c4f9…
CHAIN OK — 3 beats verified, root sha256:e9c3cb7c3260c4f9c7a86a2c68d20d4f4c187691d9da85745332b71f7af3381b
signer fingerprint (sha256 of normalized PEM): e02165204e94b1c8b70b825137673db02f663b447dcb758503f7432cc55c8661
```

Exit code 0 means the chain verified. The sample is signed by an **ephemeral
demo key** (regenerate it with `python examples/make_sample_chain.py`); real
estate bundles are signed by organ keys published in
[`szl-holdings/.github/cosign-keys`](https://github.com/szl-holdings/.github/tree/main/cosign-keys).

## Verifying a real published bundle

1. Obtain the bundle (`bundle.json`: `payloadType`, `genesis`, `beats[]`,
   `expected_root`) from the publishing surface.
2. Obtain the signer's public key PEM from `cosign-keys/<organ>.pub` in the
   `.github` repo — fetch it once, then work offline.
3. Confirm the key out-of-band: its SHA-256 fingerprint should match the
   fingerprint the publisher advertises.
4. Run the verifier as above. `CHAIN OK` plus the fingerprint you confirmed
   is the whole proof.

## What the verifier checks (fail-closed)

| Check | What it catches |
|---|---|
| DSSE signature over PAE, per beat | Any payload or `payloadType` tampering |
| `keyid` vs SHA-256 of normalized PEM | Signer/key confusion (legacy `szlholdings-cosign` keyid accepted with a note; `--strict-keyid` rejects it) |
| `prev_beat_hash` link per beat | Reorder, insertion, deletion of beats |
| `seq` == position | Replayed or swapped beats |
| Canonical-JSON byte equality | Encoding-level malleability (`--no-canonical-check` to relax) |
| Final `beat_hash` == `expected_root` | Any divergence anywhere in the chain |

Every failure exits 1 with `CHAIN FAILED — <reason>`. IO/usage errors exit 2.
Only a full pass prints `CHAIN OK` and exits 0. `--json` emits a
machine-readable verdict for CI; `--quiet` suppresses per-beat lines.

## Why offline matters

If verification required our servers, you would be trusting the thing being
verified. Here the verifier is ~200 lines you can read, the crypto is one
library call, and the only inputs are bytes you hold. Prove, don't assert.
