# Verify an SZL receipt chain offline

A stranger's guide to proving an SZL receipt chain is authentic — no SZL
infrastructure, no network calls, no trust in us required. Target: first successful verify in under 5 minutes
from a fresh clone (a target, not yet timed with outside users).

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

## Try every outcome (2 more minutes)

A verifier you have only seen succeed is a verifier you have not tested. Run
these from the same clone; each line ends with the exit code you should get.
The outputs below are real runs against the committed sample.

```bash
# 1. Tamper with one byte of beat 1, then verify  -> CHAIN FAILED, exit 1
python -c "import json,base64;b=json.load(open('examples/offline-verify-sample/bundle.json'));p=bytearray(base64.b64decode(b['beats'][1]['payload']));p[-2]^=1;b['beats'][1]['payload']=base64.b64encode(bytes(p)).decode();json.dump(b,open('tampered.json','w'))"
python examples/verify_chain_offline.py --bundle tampered.json --pubkey examples/offline-verify-sample/pubkey.pem --quiet  # expect exit 1

# 2. Ask who signed it, using the org trust manifest  -> SIGNER UNKNOWN, exit 3
curl -sSLO https://raw.githubusercontent.com/szl-holdings/.github/main/cosign-keys/MANIFEST.json
python examples/verify_chain_offline.py --bundle examples/offline-verify-sample/bundle.json --pubkey examples/offline-verify-sample/pubkey.pem --manifest MANIFEST.json --quiet  # expect exit 3

# 3. Require freshness  -> STALE, exit 5
python examples/verify_chain_offline.py --bundle examples/offline-verify-sample/bundle.json --pubkey examples/offline-verify-sample/pubkey.pem --quiet --max-age-days 30 --now 2026-11-19T00:00:00Z  # expect exit 5
```

```
CHAIN FAILED — ECDSA signature invalid
SIGNER UNKNOWN — integrity verified, but this key is not in the trust manifest; treat the receipts as unauthenticated (abstain)
STALE — newest beat is 77 days old (> 30); integrity holds, but re-fetch a current bundle before relying on it (abstain)
```

Outcome 2 is correct behaviour, not a bug: the sample is signed by a demo key
that is deliberately absent from the org manifest.

| Verdict (`--json` `verdict`) | Exit | Meaning | What to do |
|---|---|---|---|
| `PASS` | 0 | Signatures, links and root verified (and, with `--manifest`, the key is listed and valid for the beat times) | Rely on integrity; with `--manifest`, the signer is identified |
| `FAIL` | 1 | Any signature, link, digest, canonical-encoding or timestamp-format failure | Do not use the bundle |
| (usage) | 2 | Unreadable file or bad arguments | Fix the command |
| `SIGNER_UNKNOWN` | 3 | Integrity holds but the key is not in the manifest | Abstain: confirm the fingerprint out-of-band or treat as unauthenticated |
| `SIGNER_REVOKED` / `SIGNER_NOT_VALID_AT_TIME` | 4 | Key revoked, retired without a bound, or the beats claim times outside its window | Do not trust the signer identity |
| `STALE` | 5 | Integrity holds but the newest beat is older than `--max-age-days` | Abstain: fetch a current bundle |

When several apply, the more serious one wins: 1 > 4 > 3 > 5 > 0.

Malformed trust-manifest structure (root, organs, entries or fingerprint types) is a configuration error (exit 2), not an unrecognized signer (exit 3). Non-string or unrecognized status on the matching key fails closed with exit 4.

Every signed beat timestamp is checked for parseability and nondecreasing order, not just the endpoints. The first and last timestamps therefore bound every beat for optional key validity windows, but they are still signer-declared rather than independently time-attested. Invalid `--now` or `--max-age-days` arguments and malformed selected-key `not_before`/`not_after` trust-root fields are configuration errors (exit 2), not receipt-integrity failures (exit 1).

## Verifying a real published bundle

1. Obtain the bundle (`bundle.json`: `payloadType`, `genesis`, `beats[]`,
   `expected_root`) from the publishing surface.
2. Obtain the signer's public key PEM from `cosign-keys/<organ>.pub` in the
   `.github` repo — fetch it once, then work offline. Pick the key whose
   `fingerprint_sha256` in `cosign-keys/MANIFEST.json` equals the envelope's
   `keyid` (the verifier accepts the fingerprint computed with or without the
   PEM's trailing newline).
   Receipts minted by the live a-11-oy.com runtime are signed by the runtime
   key served at `https://a-11-oy.com/cosign.pub`. That is a different key from
   `a11oy-cosign`, and at the time of writing it is **not yet listed** in
   `cosign-keys/MANIFEST.json`. Until it is, a runtime receipt can pass the
   integrity check, but `--manifest` reports `SIGNER UNKNOWN` (exit 3) and you
   must confirm the runtime key's fingerprint out-of-band (step 3) before
   treating the signer as identified. If no manifest entry matches the `keyid`
   and you cannot confirm the key out-of-band, treat the receipt as
   unauthenticated: an integrity pass alone does not identify the signer.
3. Confirm the key out-of-band: its SHA-256 fingerprint should match the
   fingerprint the publisher advertises.
4. Run the verifier as above, with `--manifest MANIFEST.json`. `CHAIN OK`
   plus `SIGNER ANCHORED` (or a fingerprint you confirmed out-of-band) is the
   whole proof.

### Key lifecycle fields in the manifest (optional)

Manifest entries may carry these fields; entries without them behave exactly
as before:

| Field | Meaning |
|---|---|
| `status` | `active` (default), `retired` or `revoked`. Any other value fails closed (exit 4) |
| `not_before` | RFC 3339 UTC. Beats claiming an earlier time fail (exit 4) |
| `not_after` | RFC 3339 UTC, set when a key is retired. Beats claiming a later time fail (exit 4). A `retired` key without `not_after` fails |
| `revoked_at` | RFC 3339 UTC, informational. A `revoked` key fails for **all** beats, because beat timestamps are written by the signer and a stolen key can backdate them |

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
Only a full pass prints `CHAIN OK` and exits 0; exits 3, 4 and 5 are the
abstain and signer states in the table above. `--json` emits a
machine-readable verdict for CI; `--quiet` suppresses per-beat lines.

## What this verification does not prove

- **That the decision was right.** A valid chain proves these bytes were
  signed by this key and not altered; it says nothing about whether the
  governed action or verdict inside was correct.
- **When something really happened.** Beat `ts` values are written by the
  signer. There is no independent timestamp authority or transparency-log
  inclusion proof yet, so time-window checks catch honest mistakes, not a
  determined key thief.
- **That the key list was never changed quietly.** Key additions and removals
  are visible only in the `.github` repository's git history; no independent
  monitor watches them yet.
- **Anything about the server-side `/verify` page.** That page checks receipts
  against the key the same server publishes; it is a convenience, not
  independent verification. This offline path is the independent one.
- **Availability.** There is no published uptime target for the surfaces that
  publish bundles and keys; treat availability as unknown.

## Why offline matters

If verification required our servers, you would be trusting the thing being
verified. Here the verifier is ~200 lines you can read, the crypto is one
library call, and the only inputs are bytes you hold. Prove, don't assert.
