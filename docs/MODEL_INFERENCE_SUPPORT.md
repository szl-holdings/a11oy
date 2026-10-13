<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Model provider and support-request observations

`docs/model-inference-support.json` is the source for the A11oy model catalog and
downstream card presentation. It records public Hub provider observations and
support discussions. The reviewed source covers the **48 public model-namespace
repositories** in `docs/huggingface-ecosystem-manifest.json`. That namespace also
contains kernels, software, adapters, GGUF bundles, and NumPy artifacts; its count
is not an LLM count. Entries from the separate native-kernel namespace are not
added to the model count.

## Evidence boundaries

Each exact, case-sensitive model ID has three independent records:

| Record | Meaning | Evidence |
|---|---|---|
| `assessment` | Artifact class and a bounded qualification/compatibility note from a dated review | Exact Hub revision and immutable model-card URL |
| `inference` | Providers reported by the public Hub mapping at the observation time | Exact API URL, Hub revision, observation date, normalized capture digest |
| `support` | Actual verified submissions or prior observed discussions | Discussion URL/number, author, recorded status, and readback proof where available |

`REQUESTED` means a submission was read back. It does not establish provider
acceptance, listing, a successful model load, serving, or model qualification.
`NO_RECORDED_REQUEST` means this source contains no matching request; it is not a
claim that nobody has ever requested the model. A prior discussion does not gain
an inferred model revision, submission date, or body digest. The historical
`SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator` discussion remains in
`unmatched_prior_requests`; it is not silently mapped to `brain-navigator-r2`.

Provider mapping uses the documented
[Hugging Face Hub API](https://huggingface.co/docs/inference-providers/hub-api).
`NO_PROVIDER_MAPPING` requires an actual empty mapping object. A missing, null,
malformed, failed, or oversized response becomes `UNAVAILABLE`. A populated
mapping is `PROVIDER_MAPPING_REPORTED`, retaining each provider's reported
`live` or `staging` status. These labels describe Hub metadata. They are not
A11oy routing admission or a local model execution receipt.

The capture digest hashes canonical UTF-8 JSON containing `id`, `sha`, and the
normalized `inferenceProviderMapping` fields. It is explicitly labelled
`NORMALIZED_PUBLIC_API_FIELDS_NOT_INDEPENDENT_ATTESTATION`; it does not claim to
hash original HTTP wire bytes or provide an independent signature.

The source binds its exact model-ID set with `inventory_source.model_ids_sha256`:
SHA-256 of canonical JSON for the sorted, case-sensitive ID array. Both this
digest and exact coverage against the canonical inventory are checked. Each
provider observation and assessment has its own Hub revision; an unrelated
Space/dataset metadata refresh cannot overwrite those revisions.

## Product reads

The same source is available at:

- `GET /api/a11oy/v1/models/inference-support`
- `GET /v1/models/inference-support`
- Matching records under `inference_support` in the existing model estate and
  Series A catalog responses.

The dedicated endpoint reads committed files only, returns `Cache-Control:
no-store`, and never calls a provider, loads a model, writes an index, or signs.
Invalid or missing source returns JSON HTTP 503 with `UNAVAILABLE`. Provider
observations older than **24 hours**, or from a clock more than five minutes in
the future, become unavailable in the runtime projection. Previous reported
providers remain separately labelled as historical observations. Requests and
immutable assessment notes are retained; they do not become current serving
evidence. The file schema describes committed source, while the API also adds
derived freshness, summaries, and `runtime_qualification` metadata.

Routing, qualification, promotion, and deployment authority are always false in
this catalog. Existing model release manifests, signed-evidence requirements,
fabrication controls, and the admit contract remain authoritative. A metadata
refresh does not qualify a held-out failure or make a research artifact
promotable.

## Validate and refresh source

Validate the committed data and exact inventory coverage offline:

```bash
python -B scripts/collect_model_inference_support.py --check
python -m pytest -q tests/test_model_inference_support.py
```

Prepare current public mapping observations as a reviewable candidate:

```bash
python -B scripts/collect_model_inference_support.py --refresh \
  --output /tmp/model-inference-support.candidate.json
```

The collector uses anonymous metadata GETs, rejects redirects, has an eight-second
timeout and a 256 KiB response limit, and makes at most four concurrent requests.
Failed reads replace availability with an explicit unavailable observation; no
last-good provider is carried forward as current. Existing request evidence and
assessment notes are preserved byte-for-byte as JSON values. Changes to the
inventory's model-ID set require source review before refresh can continue.

The public-inventory maintenance workflow runs the same offline check against its
generated candidate before committing its six allowlisted inventory projections.
The drift review-branch preparer validates the existing support source against the
candidate before writing the inventory or creating Git objects. Model-ID membership
changes require source review. Adding an entry requires a dated assessment and a
real provider observation or failed lookup; neither path generates assessments or
submits support requests.
Advancing the document's generation time leaves each older observation's timestamp
and 24-hour expiry intact.

Review the candidate, update the canonical JSON through a normal PR, and run the
offline check. The canonical Space publisher remains the only automatic Space
writer. This collector creates no provider endpoint, submits no discussion,
changes no credentials, and performs no inference. There is no automatic
source-refresh claim: unreviewed candidate files do not become deployed status.

Structural validation is specified by
`docs/model-inference-support.schema.json`. `a11oy_model_support.validate_document`
also checks cross-field identities, capture digests, ordering, exact inventory
coverage, source URLs, and timestamp relationships. The module belongs to the
`services` taxonomy and is explicitly included in the runtime Docker image.
