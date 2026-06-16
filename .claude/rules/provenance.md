<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rule: provenance

The audit fiber. Modules: `szl_provenance`, `szl_dsse`, `szl_khipu*`, `szl_receipt_substrate`,
`szl_khipu_verify`. Invariant: **`receipts.in ≡ receipts.out`**.

## Rules

- **Any state change emits a Khipu receipt.** A new action path that changes state (agent step,
  verdict, deploy, ledger write) must mint a DSSE-enveloped, hash-chained receipt.
- **Never sign on a read path.** Signing belongs on writes, not GETs. Do **not** add
  sign-per-request side effects to a read handler (see the `/frontier/manifest` no-sign-on-GET
  fix — read paths use a cached/last-known digest).
- **Verify before claiming "signed".** Use `POST /khipu/verify` (or `GET /khipu/verify/{digest}`)
  to recompute and re-verify the chain. Flip a byte → `chain_intact=false`.
- **Real signature or honest UNSIGNED — never faked.** ECDSA-P256 cosign signature only when
  `SZL_COSIGN_PRIVATE_PEM` is present; when absent, the receipt is clearly labelled UNSIGNED.
  Never fabricate a signature.
</content>
