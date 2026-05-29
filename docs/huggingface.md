# Hugging Face publishing

A11oy publishes a Hugging Face payload as a discovery and diligence mirror. The
canonical source, release tags, SBOMs, SLSA provenance, and CI checks remain on
GitHub.

## Payload contents

Run:

```bash
pnpm payload:huggingface
```

The command writes `dist/huggingface/a11oy/` with:

- a Hugging Face model card (`README.md`);
- showcase, investor, verification, quickstart, deep-dive, and receipt-sample files;
- source README, roadmap, changelog, and repo map;
- deployment payload metadata under `payloads/deploy/`;
- `a11oy-metadata.json` with source commit and verification commands.

The publisher prunes stale remote files by default before uploading the
generated folder. This prevents old unsupported model-wrapper files, stale
product names, or non-reproducible hand edits from surviving on Hugging Face.

## Operational bundle

Run:

```bash
pnpm payload:bundle
pnpm payload:bundle:verify
```

The bundle command is Python-native. It builds doctrine package outputs, refreshes
`deploy/MANIFEST.json`, prepares the Hugging Face payload, and writes:

- `dist/payload/a11oy-operational-payload.tar.gz`
- `dist/payload/a11oy-operational-payload.tar.gz.sha256`

The Doctrine Build workflow uploads those files as the
`a11oy-operational-payload` GitHub Actions artifact on every matching PR or main
push. Do not paste Hugging Face tokens into chat or commit them to the repo; use
GitHub secret `HF_TOKEN` for live publishing.

## Publish from GitHub Actions

Add repository secret `HF_TOKEN` with write access to the target Hugging Face
organization or user namespace. Then run the `Publish Hugging Face Payload`
workflow manually.

Recommended inputs:

| Input | Value |
| --- | --- |
| `repo_id` | `SZLHOLDINGS/a11oy-v19-substrate` |
| `repo_type` | `model` |

The workflow creates the target repo if needed and uploads
`dist/huggingface/a11oy/`.

## Local publish

For local operator publishing:

```bash
pnpm install
pnpm test:doctrine
pnpm typecheck:doctrine
pnpm build:doctrine
pnpm ecosystem:audit
pnpm payload:manifest
pnpm payload:huggingface
python -m pip install --upgrade huggingface_hub
python - <<'PY'
import os
from huggingface_hub import HfApi

api = HfApi(token=os.environ["HF_TOKEN"])
api.create_repo("SZLHOLDINGS/a11oy-v19-substrate", repo_type="model", exist_ok=True)
api.upload_folder(
    repo_id="SZLHOLDINGS/a11oy-v19-substrate",
    repo_type="model",
    folder_path="dist/huggingface/a11oy",
    commit_message="publish a11oy operational payload",
)
PY
```

Do not commit `dist/`; the payload is generated from tracked source and deploy
metadata.

## Direct publish helper

When `HF_TOKEN` is available in the environment, publish the prepared payload with:

```bash
pnpm payload:publish:huggingface -- --repo-id SZLHOLDINGS/a11oy-v19-substrate --repo-type model
```

The helper does not print the token. GitHub Actions remains the preferred path
for secrets. Pass `--no-delete-stale` only for emergency diagnostics; normal
publishes should prune remote files that are absent from `dist/huggingface/a11oy/`.

## Naming policy

The A11oy Hugging Face packet uses the real GitHub ecosystem names and does not
use stale KORA, LUMINA, PARAGON, or active Lyte framing. Counsel, Terra, and
Carlota Jo are marked as funded-roadmap/excluded in the readiness report rather
than presented as live demo surfaces.
