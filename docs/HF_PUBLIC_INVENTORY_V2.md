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

### Revision classes

`docs/huggingface-revision-classes.v1.json` classifies rows by `(repoType, id)`, because the same id can exist as a model and as a kernel. `scripts/hf_revision_classes.py` loads it fail-closed: a missing, unreadable or invalid file is `INVALID`, never a fallback to the default class.

- `GOVERNED_EXACT`: `sha` and `lastModified` stay in semantic comparison, as for gated rows. Any head move is `INVALID` with `governed revision changed`, and `scripts/prepare_hf_inventory_refresh.py` stops with `SOURCE_REVIEW_REQUIRED` instead of proposing a routine refresh branch. Every gated row and every repository named by a `model_release/` binding must be in this class; `SZLHOLDINGS/szl-nemo` is one.
- `SOURCE_TRACKED`: the default for unlisted rows. Identical to the earlier ungated comparison above.
- `APPEND_ONLY_EVIDENCE`: reserved and unused. No file-level append proof over the Hub tree API is implemented, so the validator rejects any row that uses it. The evidence datasets therefore remain `SOURCE_TRACKED`.

Bindings are found by a fixed scan: every exact `SZLHOLDINGS/<name>` string in `model_release/**/*.json` must sit at a declared binding or reference-only location, and each binding must be cited by its exact JSON pointer in its entry's `policySource`. A new file or field that names a repository fails until it is classified.

Limits: `GOVERNED_EXACT` pins the observed head, not the revision a release manifest names, and it does not inspect the Hub file tree. MEASURED from repository bytes: the tracked szl-nemo head (`44b59052…`) already differs from `model_release/szl-nemo/release-manifest.json` `hub.revision` (`7866203c…`). The live-Hub behaviour of the new checks is MODELED from code and offline fixtures; it has not been run against the Hub. A class change is visible in the policy file and in the check report's `revisionClasses.sha256`; this code does not enforce who reviews it.

`--check` prints a labelled result. `CURRENT` exits 0; `DRIFT`, `INVALID` and `UNAVAILABLE` exit 1, as before. `UNAVAILABLE` covers only transport failures (connection, timeout, HTTP 429 or 5xx; card and revision fetches retry first, listing pages do not); HTTP 401/403/404/410, malformed responses and listing-policy violations are `INVALID`. `--report PATH` writes the same result as JSON, with each drifted row's class and `policySource`; a report that cannot be written is `INVALID`, never `CURRENT`.

The JSON schema conditionally permits a null README digest only for a gated row with the complete restricted-evidence shape. Python validators independently check the metadata digest, finite JSON values, bounded metadata size, source SHA, and observation timestamps.

## Verification

Run the offline collector, access-boundary and revision-class regressions:

```sh
python -S scripts/test_audit_huggingface_ecosystem.py
python -S scripts/test_hf_gated_public_inventory.py
python -S scripts/test_hf_revision_classes.py
python scripts/audit_huggingface_ecosystem.py --check
python scripts/build_ecosystem_stage_matrix.py --check
node scripts/validate_huggingface_ecosystem_schema.mjs
```

Only the last three commands contact the Hub or inspect derived evidence; the three Python test suites use offline fixtures, plus the tracked snapshot, revision classes and `model_release/` files read from disk. The permanent `Public Hub inventory access contract` CI job requests no secrets and needs no package installation. The stage matrix must carry the same `observedAt` value and Hugging Face public counts as the manifest, so schema migration and inventory refreshes cannot leave operational evidence stale.

Generation is an explicit source update. Commit the generated snapshot and its derived stage matrix through the normal reviewed workflow; never generate over a tracked manifest during a `--check` invocation. A successful public-inventory check does not authorize deployment or use of restricted model files.
