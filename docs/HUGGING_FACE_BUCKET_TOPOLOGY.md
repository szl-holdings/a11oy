# Hugging Face Bucket topology for SZL-Forge

Status: **CREATED_PRIVATE_EMPTY_VERIFIED**. The three private buckets were created through the locally authenticated Hugging Face CLI and read back as private, empty (`0` bytes, `0` files). No object was uploaded and no model, dataset, Space, paper, or release was published.

## Recommendation

Use Hugging Face Storage Buckets as a fast, mutable working plane around SZL-Forge—not as the public source of truth. Hugging Face describes Buckets as non-versioned, mutable object storage for checkpoints, logs, intermediate artifacts, and changing file collections. Finished models, datasets, and Spaces belong in versioned Hub repositories with cards, history, collaboration, and stable revisions. See the official [Storage Buckets](https://huggingface.co/docs/hub/storage-buckets), [access patterns](https://huggingface.co/docs/hub/storage-buckets-access), [S3 compatibility](https://huggingface.co/docs/hub/storage-buckets-s3), and [security](https://huggingface.co/docs/hub/storage-buckets-security) documentation.

The proposed topology deliberately separates three failure domains:

1. `SZLHOLDINGS/szl-forge-build-staging` — checkpoints, optimizer state, candidate adapters, and build receipts.
2. `SZLHOLDINGS/szl-forge-eval-staging` — held-out outputs, benchmark bundles, red-team findings, and qualification receipts.
3. `SZLHOLDINGS/szl-forge-runtime-evidence` — sanitized traces, model-load observations, restart evidence, receipt batches, and OpenTelemetry exports.

All three are noncanonical, private, and currently empty. This separation prevents a training writer from quietly changing evaluation evidence and prevents runtime telemetry credentials from becoming model-release credentials.

## Completion barrier

Every upload uses a never-reused attempt prefix. Payload objects and a DSSE-signed manifest are written first. An independent verifier then downloads every payload and the manifest, recomputes SHA-256 and byte counts from the returned bytes, validates the manifest signature, and emits a signed readback receipt.

Only after that verification may the restricted marker writer create `_control/COMPLETED.json` as the final object. The marker binds the exact manifest digest, readback-receipt digest, verifier key, bucket, and attempt. It is conditionally created, signed by the verifier, and read back again. Consumers fail closed unless the marker, signatures, full object readback, rights bindings, source revision, and requested candidate identity all match.

Object presence, a UI badge, filename, `latest`, ETag, bucket audit event, or even a valid completion marker is not release approval. Any overwrite or deletion invalidates the staged attempt.

## Authority boundaries

- The **bucket stager** can write one payload/manifest prefix but cannot write `COMPLETED`, approve, or publish.
- The **independent readback verifier** can read and conditionally create only the completion marker; it cannot stage payload or approve.
- The **release approver** signs a human approval decision but has no bucket or Hub-repository write permission.
- The **canonical Hub publisher** can publish only the exact approved digest to an exact versioned model, dataset, or Space repository; it cannot self-approve.
- The **runtime evidence writer** can stage sanitized runtime batches but cannot complete, approve, or publish them.

Canonical promotion requires completion/readback, rights and provenance, exact base/license lineage for models, held-out qualification, security scanning, and separate signed approval. The destination revision is then independently read back before a collection is updated. GitHub releases and Zenodo archives remain separate archival authorities, never bucket aliases.

## Content that never enters these buckets

Tokens, S3-derived credentials, private signing keys, raw PII/PHI/PCI, customer-confidential content, rights-unknown corpora, unadmitted Brain rows, protected evaluation keys in training, unqualified weights, unsafe executables, unsanitized telemetry, the only canonical copy of any artifact, and mutable aliases presented as identity are forbidden without exception.

The exact topology, object protocol, forbidden set, authority matrix, promotion gates, claims boundary, and official-source crosswalk are in [the contract](../model_release/szl-hf-bucket-topology.json), validated by [its JSON Schema](../model_release/szl-hf-bucket-topology.schema.json) and focused contract tests.
