# Provenance and evidence boundary

This package is derived only from content-addressed artifacts already present
in the A11oy repository. The builder verifies their receipts before copying or
deriving data.

## Formula-admission snapshot

- Crosswalk and tranche commit:
  `e4d269b309fe67264f1dfe64a65c3c5fb6ecf570`
- Reconciled admission manifest and receipt commit:
  `b7b0f2996edf674d7365d37112371fa6690e7c0e`
- Crosswalk: `research/formula-training-admission/formula-id-crosswalk.json`
- Tranche: `research/formula-training-admission/admission-tranche.jsonl`
- Admission manifest: `research/formula-training-admission/admission-manifest.json`
- Receipt: `research/formula-training-admission/artifact-receipt.json`

The four packaged source files are byte-identical copies. Their content
digests are recorded in both the source receipt and `release-manifest.json`.
Each derived queue record carries the original row receipt, crosswalk receipt,
and artifact receipt.

## Brain-evidence snapshot

- Source commit: `706894f52a45f80a5c440aeaafc52eec33fafc23`
- Protocol: `brain-canonical-retrieval-pilot-v1`
- Manifest: `research/brain-evidence-admission/evidence-manifest.json`
- Results: `research/brain-evidence-admission/evaluation-results.json`

Only summary counts, metrics, receipts, and limitations are copied into the
release candidate. The package contains no Brain document or query text. The
pilot is a bounded local measurement, not independent validation.

## Transformation

`build_package.py` performs four deterministic steps:

1. verifies source file and canonical-content receipts;
2. copies the three formula-admission artifacts byte for byte;
3. maps each crosswalk status and reason to an explicit evidence obligation;
4. writes the release manifest, schemas, and whole-package checksums.

No source status, locked count, proof credit, admission decision, or training
split is altered. No cryptographic signature is claimed: the inherited source
receipt is explicitly `UNSIGNED_CONTENT_RECEIPT`.
