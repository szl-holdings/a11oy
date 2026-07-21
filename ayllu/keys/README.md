# AYLLU council verifying keys

## `council-runtime-2026-07-21.pub` (ECDSA P-256)

The public key that verifies the DSSE council receipts emitted by the live
a11oy Space (`POST /api/a11oy/v1/ayllu/council`), pinned here so the wall
(`/api/ayllu/wall`) and the offline verifier
(`scripts/verify_ayllu_council_receipt.py`) can fail closed against it.

**Provenance (stated honestly, 2026-07-21):**

- The live Space signs with the `SZL_COSIGN_PRIVATE_KEY_PEM` runtime secret.
  Its envelopes carry the keyid **label** `szlholdings-cosign`, but the
  signatures do **NOT** verify against the published org key at
  `szl-holdings/.github/cosign.pub` — the Space's own public verifier
  (`/api/a11oy/v1/verify/receipt`) reports the same `MISMATCH`.
- This public key was therefore **recovered from two independent live council
  signatures** (ECDSA public-key recovery over the DSSE PAE bytes; the two
  candidate sets intersect in exactly ONE point) and cross-checked against
  both receipts. Recovery uses only public signature material.
- **Owner action pending:** reconcile the Space's signing secret with the
  published `cosign.pub` (or rotate/republish), then re-pin here. Until then,
  verification against this pin proves "signed by the a11oy runtime key and
  unaltered" — it does not prove custody of the published org key.

Fingerprint (sha256 of the PEM bytes as committed):
see `sha256sum council-runtime-2026-07-21.pub`, also surfaced live in the
wall's `keyHonesty.fingerprintSha256`.
