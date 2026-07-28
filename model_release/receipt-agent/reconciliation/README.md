# ReceiptAgent artifact-binding reconciliation

This directory preserves one narrow, offline reconciliation of the public
`SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent` candidate. It does not rerun model
inference and does not train, upload, promote, or deploy anything.

The evidence deliberately separates three claims:

1. **Receipt signature validity.** The qualification run verified both
   repository-declared Ed25519 wrappers and their training-to-evaluation chain.
   The key remains repository-declared rather than independently pinned.
2. **Exact qualified artifact binding.** The measured qualification loaded
   revision `fa73dc1bd8eeece727d0b5c1db52448ec0703e8b`, checked raw SHA-256 for
   `model.safetensors` and `adapter/adapter_model.safetensors`, and separately
   checked the original signer's
   `SHA256(UTF8(basename) || raw file bytes)` digest. Those digest domains are
   different by design. The reconciler reconstructs each canonical Git LFS
   pointer from the measured raw SHA-256 and byte count, then verifies its Git
   blob SHA-1 against the frozen qualified/public trees. The frozen raw commit
   objects are hashed back to both declared revisions, and every serialized
   root/subtree is hashed back to the tree identity named by its commit.
3. **Current public-head equivalence.** At observed public head
   `2e62cb5f8e6a17052da532305a467861094a2109`, all 12 inference-bearing Git
   blobs equal the qualified revision. A complete walk of both hash-bound trees
   proves that the only repository blob delta is the additive, non-inference
   `SZL_ESTATE_MANAGED.json` marker.

The resulting state is
`ARTIFACT_BYTES_RECONCILED_MEASURED_NOT_PROMOTED`. It does not establish hosted
serving, general quality, autonomous safety, independent owner identity, or
promotion readiness. A later public-head revision is not automatically trusted;
the runtime fails closed until a new frozen reconciliation is reviewed.

## Offline check

```powershell
python model_release/receipt-agent/reconciliation/reconcile_artifact_binding.py `
  --fixture model_release/receipt-agent/reconciliation/observed-hf-tree-fixture.v1.json `
  --qualification-receipt model_release/receipt-agent/qualification/fa73dc1-cpu-qualification-receipt.json `
  --check model_release/receipt-agent/reconciliation/receipt-agent-artifact-reconciliation.v1.json
```

The check performs no network access. Negative tests mutate the qualification
self-digest, digest-domain vectors, raw artifact identity, signature evidence,
revision commit objects, serialized trees, and inference-bearing Git blobs;
every mutation must refuse.
