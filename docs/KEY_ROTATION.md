<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# KEY_ROTATION ledger — a11oy verifiable-corpus cosign signing keys

Human-readable companion to the machine-readable `key_rotation` and `trusted_keys`
blocks in [`.github/hf-corpus-guards.json`](../.github/hf-corpus-guards.json). The
guard is the source of truth; this file explains *why* the corpus trusts more than
one key.

## Why a multi-key trust set

The public dataset `SZLHOLDINGS/a11oy-verifiable-corpus` (prefix `receipts/`)
publishes DSSE receipts signed with the szl-holdings org cosign key. The
`HF Corpus Re-verify` CI job re-verifies every published receipt's signature.

In 2026-06 the org **rotated** its cosign signing key. A single-key pin cannot be
honest across a rotation: pinning the old key breaks the new receipts; pinning the
new key breaks the historical ones. So the guard verifies each receipt **per-record
against the specific key it was actually signed with**, drawn from a **documented
trust set** of both the historical and the current org keys. This is key rotation,
not tamper — content-address integrity is intact for all 104 records (0 mismatches).

## Trusted keys

| Role | Fingerprint (`sha256` of PEM) | Valid | Records |
|------|-------------------------------|-------|---------|
| historical CI signer | `421a1422ebb2…c067e1e` | 2026-06-12 → 2026-06-23 | first 63 ecdsa receipts |
| current org signer   | `d3028f8aecd0…91bcf71` | 2026-06-27 → present     | newest 38 ecdsa receipts |

The current-org key is the one published at
`https://raw.githubusercontent.com/szl-holdings/.github/main/cosign.pub` and embedded
in `szl_dsse.COSIGN_PUBLIC_PEM`. The re-verify guard cross-checks that the live
cosign.pub is a member of the trust set on every run.

## Rotation events

- **2026-06 cosign-key rotation** (Incident #325): `421a1422ebb2…` → `d3028f8aecd0…`,
  observed between 2026-06-23 and 2026-06-27. Both keys are legitimate, documented
  org signers. The rotation does **not** invalidate the 63 historical receipts nor
  the 38 new ones — every one verifies under the specific key it was signed with.

## Quarantined orphans (NOT trusted)

Two receipts (published 2026-06-18) were signed by a **transient ephemeral CI-pod
key** (`76199818b3b6…`) that is **not** a documented org key:

- `4bfa222fdfb9707d173a59fa1405ab04dbf728b4ad99cf2b37b34512966a7dc8`
- `b88484d37568e3d057eeceb9259356f68cc541b76ef7536e1431fb10aafae241`

Their **content-address integrity is intact** (not tamper) but their signature
cannot be attributed to a trusted org key. Per Incident #325 they are **documented
orphans**: kept (not deleted), excluded from the trusted-verify set, and reported
explicitly by the guard as `quarantined`. This is documentation of a known accepted
orphan — **not** a blind allow-list of bad ids. The guard still fails loudly if
either one is tampered, if its signing key is not the documented ephemeral key, or
if it unexpectedly begins verifying under a trusted key.

## Root cause closed going forward

`szl_corpus_publish.py`'s verify-before-publish gate now re-verifies each signed
envelope against this **same trusted keyset** before publishing. A receipt signed
with an untrusted/transient key (the class that produced the two orphans) can no
longer enter the corpus — proven by `scripts/test_szl_corpus_publish_gate.py`.
</content>
