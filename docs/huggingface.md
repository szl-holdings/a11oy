# Hugging Face publishing

A11oy publishes a discovery and diligence payload to the fixed existing model
repository `SZLHOLDINGS/a11oy-v19-substrate`. It is a source and deployment
documentation package, with no model weights or inference qualification. GitHub
remains the canonical source for release tags, SBOMs, provenance and CI checks.

## Payload contents

The existing stager creates `dist/huggingface/a11oy/`:

```bash
pnpm payload:huggingface
```

The folder contains the model card, showcase and diligence documents, receipt
samples, the public ecosystem inventory, selected canonical source documents,
deployment manifest closure, build inputs and source-bound metadata. It is a
complete package operation; publishing its card also updates the other declared
payload files.

The publisher regenerates this same projection in an isolated temporary folder
and requires exact path and byte equality with the prepared folder. It checks
the source revision and the card's existing Apache-2.0 license against the
canonical license. Do not commit generated `dist/` files.

## One existing writer, one exact parent

`scripts/publish_huggingface_payload.py` serves both the existing manual
workflow and the local operator CLI. Both accept only the fixed model target
and require the exact current 40-character Hub parent revision. The default is
a read-only plan; mutation requires explicit `--apply`.

The publisher requires a clean checkout of the currently observed canonical
GitHub main commit and native valid signature evidence. It refuses dirty input,
ignored/untracked files inside copied source trees, source-tree symlinks,
index flags that conceal or omit tracked files, malformed paths and oversized
inventories. Canonical main is observed again
immediately before an apply. That observation is dated evidence, not an atomic
lock on a different provider.

The read-only plan lists every payload path, size and SHA-256 digest, plus the
exact parent bytes of any existing `bom/model-bom.cdx.json` and
`.gitattributes`. Those two paths remain outside this payload writer's
body set. Preserving them does not assert who owns them. Other remote paths
absent from the prepared package stop the operation for separate source review.

An apply submits one add/update-only Hub commit bound to the selected parent.
It never creates a repository, deletes a file, changes visibility, accepts
gating terms, restarts a Space or rebases after a parent conflict. It then reads
the complete file inventory and every expected byte at the returned immutable
commit, including the preserved BOM/provider files. A readback failure is
reported as unverified even if the commit already exists. A successful receipt
does not establish model deployment, inference or runtime readiness.

The previous default pruning behavior and the `--no-delete-stale` switch
are retired. An old invocation without an explicit parent now fails before a
Hub mutation.

## Ecosystem evidence

```bash
pnpm hf:ecosystem:write
pnpm hf:ecosystem:audit
```

The write command records actual anonymous, author-filtered public inventory,
repository types, source links, guardrails, card semantics and UTC observation
time. Private repositories are outside this predicate. The audit rejects
incomplete/malformed evidence, membership or card-semantic drift and invalid
revision changes. Keep the generated manifest and derived documents reviewed
in GitHub; do not silently overwrite them during a publication.

## Existing manual GitHub workflow

Use the existing **Publish Hugging Face Payload** workflow
(`.github/workflows/huggingface.yml`) on canonical `main`.
Its existing doctrine, ecosystem, readiness, payload, stage-matrix and schema
guards remain ahead of publication. The same offline additive-publisher
regressions run before the provider step. The workflow uses the existing
repository `HF_TOKEN` secret and `contents: read`; this change introduces
no credential or GitHub write permission.

| Input | Value |
| --- | --- |
| `repo_id` | `SZLHOLDINGS/a11oy-v19-substrate` (only allowed target) |
| `repo_type` | `model` (only allowed type) |
| `expected_revision` | Freshly observed, operator-reviewed full Hub commit SHA |
| `apply` | `false` for a plan; `true` for the full additive package |

A plan or apply can fail because source evidence changed, the selected parent
advanced, the credential is unavailable, a remote path is unaccounted for, or
another existing validation is unsatisfied. None of those failures authorizes a
second writer, a different token, a skipped guard or an automatic retry.

## Existing local operator CLI

The same helper is available locally with its source and payload guards.
Start from a clean, signed, current canonical main checkout,
use the existing authorized HF credential, and run the existing validation
sequence before staging or publication:

```bash
pnpm install --frozen-lockfile
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
pnpm ecosystem:audit
pnpm ecosystem:readiness
pnpm payload:verify
pnpm hf:ecosystem:audit
python3 scripts/build_ecosystem_stage_matrix.py --check
node scripts/validate_huggingface_ecosystem_schema.mjs
pnpm payload:huggingface
python3 -m unittest discover -s tests -p test_publish_huggingface_payload.py
```

With `huggingface_hub` installed, record and review the actual parent and
plan using the existing helper:

```bash
python3 scripts/publish_huggingface_payload.py \
  --repo-id SZLHOLDINGS/a11oy-v19-substrate \
  --repo-type model \
  --expected-revision "$REVIEWED_HUB_PARENT"
```

Only an authorized operator applies the reviewed package by adding
`--apply` with the same parent. The helper's source, closure and license
checks are enforced in both modes; the operator must also retain evidence that
the preceding doctrine/ecosystem validation sequence passed. A main or Hub
revision change requires fresh review, never an automatic replacement parent.

## Operational bundle

```bash
pnpm payload:bundle
pnpm payload:bundle:verify
```

The existing bundle builder compiles the doctrine packages, refreshes the
deployment manifest and produces the operational tarball plus checksum. The
Doctrine Build workflow retains its artifact publication behavior. Bundle
generation and model-payload publication remain distinct actions.

## Naming and qualification

The package uses canonical GitHub ecosystem names. Existing readiness reports
and their funded-roadmap/excluded classifications remain authoritative. Card
presentation, a public repository, a provider support request or a successful
byte-preserving upload never upgrades those classifications.

## API contract references

- [Hub commit API and parent binding](https://huggingface.co/docs/huggingface_hub/package_reference/hf_api#huggingface_hub.HfApi.create_commit)
- [Immutable revision file downloads](https://huggingface.co/docs/huggingface_hub/package_reference/file_download#huggingface_hub.hf_hub_download)
