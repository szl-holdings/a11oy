# Lyte v2 public-witness identity contract

The existing public-estate witness consumes the canonical Lyte build response;
it does not invent a new product identity or publication path. This source repair
continues A11oy issue #2010 and changes neither the estate manifest nor transport.

## Producer and consumer

Inspected producer: `szl-holdings/lyte-services` revision
`445c24c5a2ad314775af9a463a7d26acb910a5f1`, `lyte/api/routes_health.py`,
Git blob `b0e981fb04d616ae8fcc076a5f4ca0bd866418f5`.
It returns `szl.lyte-build/v2`, not the retired generic `szl.build-info/v1`
shape. Its source names are literal `LYTE_SOURCE_REVISION`, `SOURCE_REVISION`,
`GITHUB_SHA`, and `source_revision.txt`, not env-prefixed or container-file aliases.

The Lyte-specific adapter requires exact agreement among source, runtime, build,
and product repository/revision fields. It rejects invalid-source observations,
multiple distinct revisions, missing fields, malformed digests, unknown schemas,
unknown origins, duplicate origins, whitespace normalization, boolean/integer
lookalikes and enabled public effectors. Public human approval remains required.

The deployed profile still requires the primary `LYTE_SOURCE_REVISION` binding.
The producer also supports local/file-only configurations, but those configurations
do not qualify this narrower public profile. No extra environment variable is
introduced by the repair. Input observations are not rewritten or mutated.

## Evidence boundary

Identity-shape validation is not authenticated producer attestation. The existing
GitHub default-tip proof and separate Hugging Face provider-revision observation
remain mandatory. A failed route, provider HTTP error or stale source remains a
failed surface row. A provider-observed HF tip is not proof of all deployed file
bytes. No inference quality, tenant acceptance, production authority, training,
new credentials, mutation or estate-wide completion follows from these tests.

## Verification

From a complete checkout:

```bash
python -m pytest tests/test_public_estate_live_witness.py -q
python -O -m pytest tests/test_public_estate_live_witness.py -q
```

The existing public-estate workflow selects both changed Python paths and runs
these tests. No workflow or assertion is disabled. Tests use synthetic producer
metadata and recording transport substitutes; they do not call the public app or
provider. Actual live verification must retain its own run/source/revision and
failed observations. Historical failed receipts remain unchanged.

The implementation session matched the complete baseline witness, test module and
manifest to their Git blobs before testing. Baseline: 39 cases passed. Updating the
fixtures to the actual producer shape exposed six failures against the old witness.
After repair: 90 cases passed normally and under optimized Python 3.13.5, zero
skips. These are the same 90 cases per mode, not 180 unique tests. Full hosted
repository results and current public-source alignment require separate evidence.
