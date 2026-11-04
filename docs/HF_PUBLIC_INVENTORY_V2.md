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

The four release sources (`szl-nemo/release-manifest.json` `/hub/repository`, `hf-promotion/promotion-manifest.json` `/candidates/*/canonical_target`, `szl-forge-family.json` `/profiles/*/hf_target`, `receipt-agent/release-manifest.json` `/hf_artifact_family/*/target_id`) and their exact namespaces are fixed in `REQUIRED_BINDING_SOURCES` in the code, so a policy-only edit cannot drop, re-namespace or null-map them. In every binding source only the `COLLECTION` kind may map to no namespace. The other binding sources are declared by the policy file itself: a policy-only edit can still move one of them to `referenceOnlySources` or change its namespace, and only review of that file catches it.

Limits: `GOVERNED_EXACT` pins the observed head, not the revision a release manifest names, and it does not inspect the Hub file tree. MEASURED from repository bytes: the tracked szl-nemo head (`44b59052…`) already differs from `model_release/szl-nemo/release-manifest.json` `hub.revision` (`7866203c…`). The live-Hub behaviour of the new checks is MODELED from code and offline fixtures; it has not been run against the Hub. A class change is visible in the policy file and in the check report's `revisionClasses.sha256`; this code does not enforce who reviews it.

`--check` prints a labelled result. `CURRENT` exits 0; `DRIFT`, `INVALID` and `UNAVAILABLE` exit 1, as before. `UNAVAILABLE` covers only transport failures (connection, timeout, HTTP 429 or 5xx; card and revision fetches retry first, listing pages do not); HTTP 401/403/404/410, malformed responses and listing-policy violations are `INVALID`. `UNAVAILABLE` means drift was not evaluated (UNKNOWN), never that there is no drift. Canonical rendering and every per-row check that needs no network (presence, gate policy, restricted and governed revisions, `lastModified` consistency) run for every row before any historical revision is fetched, so an outage on one row cannot hide a revision change already visible in the live listing. A README fetch that fails while the live inventory is still being built stops before any per-row comparison and is `UNAVAILABLE`. `--report PATH` writes the same result as JSON, with each drifted row's class and `policySource`; a report that cannot be written is `INVALID`, never `CURRENT`.

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

## Rolling review branch

When the `HF Ecosystem manifest drift` check is red and a fresh candidate passes every preflight, `scripts/prepare_hf_inventory_refresh.py` proposes it on one branch, `szl/hf-inventory-refresh`. The check, its accepted state (`CURRENT` only) and every preflight are unchanged; nothing is merged automatically.

- **Absent branch:** one creation, no retry, then a readback.
- **Existing branch:** each commit ahead of main must have author `github-actions[bot]`, committer `web-flow`, a GitHub-verified signature, the refresh message template, a first-parent diff inside the six generated files and, for an update, a second parent equal to the previous head. Any other commit stops the run with `ROLLING_BRANCH_HAS_FOREIGN_COMMITS` and nothing is written. The bot's existing single-parent commits have this author, committer, verified signature and message (MEASURED on 2026-11-03 by a read-only GitHub compare of `517273ad`). No two-parent update commit exists yet, so that path is MODELED.
- **Update:** a fast-forward only (`PATCH` with `force:false`), never retried. A rejection ends as `REF_WRITE_UNCERTAIN` with a readback. GitHub refusing a non-fast-forward is MODELED from its REST documentation; the offline tests use fakes and do not measure it.
- **Held:** a candidate semantically equal to the branch head writes nothing, and an open pull request from the branch with auto-merge enabled or an approving review stops the update.
- **One pull request per merge cycle:** the repository deletes a branch on merge (`delete_branch_on_merge=true`, MEASURED 2026-11-03), so the next refresh creates the branch again.
- **"Update branch" stops the bot:** that button adds a commit authored by the person, so the next run stops. To restart, merge or close that pull request and delete the branch.
- **Required checks may not run:** ref updates made with `GITHUB_TOKEN` do not start `pull_request` workflows (MODELED), so a maintainer may need to re-run them on the pull request.

`HF inventory review branch prune` (`.github/workflows/hf-inventory-branch-prune.yml`) runs only on manual dispatch and defaults to a dry run. It deletes a legacy `szl/hf-inventory-<source>-<candidate>` ref only when all of these hold:

- no open pull request uses it;
- every commit on it passes the same commit predicate;
- main already carries a newer `observedAt`.

It never deletes the rolling branch. Its receipt lists every ref with its sha and the reason it was kept or pruned. The receipt is hash-chained and DSSE-enveloped, and stays UNSIGNED unless the runtime holds a signing key; the workflow passes none. The manifest of each ref marked PRUNE is archived beside the receipt (90-day artifact retention). A ref whose commits include a person's merge is kept.
