# Sigstore Rekor anchoring

Each consensus receipt can be anchored to the Sigstore Rekor transparency log as
a DSSE bundle. Rekor v0.10+ supports DSSE entries; a single consensus receipt
becomes ONE Rekor entry carrying all witness signatures. The returned
`logIndex` is the publicly cross-verifiable consensus proof.

## Honest support level
- DSSE bundle with a single signature: broadly supported.
- DSSE bundle carrying multiple independent signatures (one per witness): the
  cleanest path is to anchor the canonical receipt's PAE as a hashedrekord /
  intoto DSSE entry; multi-subject verification is performed by re-running the
  reference verifier against each witness's published public key (this repo's
  `tally`). Rekor provides INCLUSION + TIMESTAMP; per-witness signature validity
  is established by the verifier, not Rekor.

See the SZL Khipu Consensus operational ledger for live `logIndex` examples.
