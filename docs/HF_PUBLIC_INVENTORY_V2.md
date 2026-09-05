# Public Hugging Face inventory — schema version 2

The source-controlled inventory is an observation of the unauthenticated public Hub APIs. It is not the authenticated organization total, a model benchmark, a weight-integrity certificate, or production-readiness approval.

## Why version 2 exists

A repository can be publicly listed while its files require an approved, authenticated user. Treating every listed repository as a publicly downloadable README caused the inventory audit to terminate with HTTP 401. Disabling the repository gate or silently excluding the repository would hide the real state.

Version 2 retains that repository, preserves its public identity, gate flag, source revision, timestamps, tags, and license metadata, and explicitly limits what was observed.

## Reading an inventory row

An ungated row retains the existing `cardSemanticSha256` contract: the normalized README at an exact revision is hashed. The pre-existing missing-README behavior remains an empty-card digest; it is not evidence of weights or inference.

A gated row has `cardSemanticSha256: null` and a required `cardObservation`:

```json
{
  "state": "ACCESS_RESTRICTED",
  "scope": "PUBLIC_METADATA_ONLY",
  "gateMode": "auto",
  "metadata": null,
  "metadataSha256": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
}
```

The example commits the JSON value `null`, meaning that no `cardData` object was present in the public listing. It does not mean the README is empty. When the listing exposes a `cardData` object, the exact public object and its canonical JSON digest are retained instead. This digest is never a README-body, model-weight, signature, or training-evidence digest.

Gate modes `auto`, `manual`, and provider boolean `true` (normalized to `enabled`) are supported. Unknown gate states fail closed. No gate approval, access request, credential lookup, protected-file download, or model execution is performed by this collector.

## Change detection

Ungated cards retain historical-revision verification and semantic README comparison. The existing narrowly defined provider-generated dataset tag exclusions remain unchanged.

Gated rows are stricter about source revisions: their `sha` and `lastModified` remain in semantic comparison. A changed gated revision requires a reviewed snapshot refresh because an unreadable README change cannot honestly be classified as source-only. Gate-mode, public metadata, tag, inventory, and visibility changes are not ignored. Unexpected HTTP 401/403 responses for an allegedly ungated card remain blocking errors.

The JSON schema conditionally permits a null README digest only for a gated row with the complete restricted-evidence shape. Python validators independently check the metadata digest, finite JSON values, bounded metadata size, source SHA, and observation timestamps.

## Verification

Run the original 17 regressions and the 14 access-boundary regressions:

```sh
python -S scripts/test_audit_huggingface_ecosystem.py
python -S scripts/test_hf_gated_public_inventory.py
python scripts/audit_huggingface_ecosystem.py --check
node scripts/validate_huggingface_ecosystem_schema.mjs
```

Only the last two commands observe the existing manifest or public services; the two Python test suites use offline fixtures. The permanent `Public Hub inventory access contract` CI job requests no secrets and needs no package installation.

Generation is an explicit source update. Commit the generated snapshot through the normal reviewed workflow; never generate over a tracked manifest during a `--check` invocation. A successful public-inventory check does not authorize deployment or use of restricted model files.
