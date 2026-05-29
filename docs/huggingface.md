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

- a Hugging Face dataset card (`README.md`);
- source README, roadmap, changelog, and repo map;
- deployment payload metadata under `payloads/deploy/`;
- `a11oy-metadata.json` with source commit and verification commands.

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
