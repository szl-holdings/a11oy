# Brain row evidence assembler

`szl_brain_row_evidence_assembler.py` is the bounded offline bridge between the
9,464-row M1 Brain ledger and the existing row-admission engine. It does not
scrape evidence, decide that a license applies, clear privacy, appoint a
reviewer, admit a row, train a model, sign an index, publish, or promote.

## Trust boundary

The operator supplies three independent inputs:

1. `model_release/m1/brain-ingest-ledger.jsonl` (exactly 9,464 unique rows);
2. one canonical-JSON DSSE envelope with payload type
   `application/vnd.szl.brain-row-evidence-index.v1+json`;
3. the explicitly trusted ECDSA P-256 public key and expected key ID.

The signed payload is `szl.brain-row-evidence-index.v1` and binds the exact M1
ledger SHA-256. Every evidence row is keyed by the exact pair
`node_id + content_sha256` and carries all candidate `source`, `rights`,
`privacy`, `contamination`, `review`, and `split` fields. Those values must be
present in the signed payload. The assembler never supplies a default for any
of them. Duplicate keys, unknown keys, node/hash mismatches, non-canonical
payloads, malformed fields, ledger drift, key-ID drift, and signature failure
all refuse the entire operation.

The index and public PEM are each read exactly once. Verification and manifest
hashes use those same bytes; file identity, size, and modification time must
remain stable across the read. This prevents a later path replacement from
changing the receipt identity after verification.

## Outputs

The output directory contains:

- `brain-training-candidate.v2.jsonl` — joined M1 content and signed evidence;
  every row remains an **unadmitted candidate** for
  `szl_brain_training_admission.py`;
- `brain-row-evidence-gap-queue.v1.jsonl` — only a domain-separated SHA-256 of
  the `node_id + content_sha256` pair and the missing-evidence code; it never
  exposes the node ID, content fingerprint, canonical content, provenance,
  rights, privacy, or reviewer data. An authorized offline operator can
  recompute the opaque key from the M1 ledger when reconciling the queue;
- `brain-row-evidence-assembly-manifest.v1.json` — source, signature, key,
  coverage, and output digests plus explicit non-claims.

An empty signed evidence index therefore produces zero candidates and 9,464
gaps. It does not turn unknown evidence into a training permission.

## Offline invocation

```powershell
python szl_brain_row_evidence_assembler.py `
  --signed-evidence-index C:\evidence\brain-row-evidence.dsse.json `
  --public-key C:\evidence\brain-review-root.pub.pem `
  --expected-keyid brain-review-root-2026-01 `
  --output-dir C:\evidence\assembled
```

The next operation is a separate, explicit run of the admission CLI with its
policy root, reviewer allowlist, evidence files, split ledger, and training
enablement controls. Successful assembly alone is never a training receipt.
