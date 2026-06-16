# Publish checklist — `szlholdings-orbital` HF Space

This directory (`spaces/orbital/`) is the **complete, ready-to-push** content for a
dedicated public Hugging Face **static** Space that mirrors the live
`a11oy.net/orbital` MODELED orbital-compute showcase.

The sandbox that prepared this **could not push to Hugging Face directly** (no
`hugging_face` connector in the build env). The founder/parent agent should push
it with the steps below. Everything needed is already in this folder — 0 runtime
CDN, three.js vendored, live-endpoint fetch with a baked SAMPLE fallback.

## Folder contents (push all of these to the Space root)

```
spaces/orbital/
├── README.md                     # HF Space card — frontmatter: sdk: static, app_file: index.html
├── index.html                    # the showcase (entry point)
├── vendor3d/
│   ├── three.module.min.js       # three.js r160 (MIT) — vendored, 0 runtime CDN
│   └── OrbitControls.js          # three.js addon (MIT)
└── data/
    ├── topology.sample.json      # baked MODELED topology (live-box fallback, captured 2026-06-16)
    └── projection.sample.json    # baked MODELED projection (live-box fallback, captured 2026-06-16)
```

## Option A — publish as a NEW dedicated Space (recommended: `SZLHOLDINGS/orbital`)

> NOTE on naming: the brief says "szlholdings-orbital". On HF the org is
> `SZLHOLDINGS`, so the Space ID is `SZLHOLDINGS/orbital` and the host becomes
> `szlholdings-orbital.hf.space` (the org-slug + space-name join). Use whichever
> the founder prefers; update the README table + GitHub README link if the final
> slug differs from `szlholdings-orbital.hf.space`.

```bash
# Requires HF_TOKEN with write access to the SZLHOLDINGS org.
python -m pip install --upgrade "huggingface_hub>=0.23"
python - <<'PY'
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ["HF_TOKEN"])
repo_id = "SZLHOLDINGS/orbital"          # → https://huggingface.co/spaces/SZLHOLDINGS/orbital
api.create_repo(repo_id, repo_type="space", space_sdk="static", exist_ok=True)
api.upload_folder(
    repo_id=repo_id,
    repo_type="space",
    folder_path="spaces/orbital",
    commit_message="publish MODELED orbital-compute roadmap showcase (mirrors a11oy.net/orbital)",
)
print("published:", "https://huggingface.co/spaces/" + repo_id)
PY
```

Or with the CLI:

```bash
huggingface-cli login            # paste HF_TOKEN (write)
huggingface-cli repo create orbital --type space --space_sdk static -y --organization SZLHOLDINGS
huggingface-cli upload SZLHOLDINGS/orbital spaces/orbital . --repo-type space \
  --commit-message "publish MODELED orbital-compute roadmap showcase"
```

## Option B — fold into the existing `SZLHOLDINGS/a11oy` Space

The existing `SZLHOLDINGS/a11oy` Space is a **Docker** Space running `serve.py`,
which already serves `/orbital` live. A static mirror is redundant there; prefer
Option A for a clean, dedicated public URL. (No action needed in the a11oy Space —
`/orbital` is already live on it.)

## Verify the Space renders (no white screen)

After the build finishes (static Spaces build in seconds):

```bash
SPACE=https://szlholdings-orbital.hf.space     # adjust to the final slug
curl -s -o /dev/null -w "index %{http_code}\n"            "$SPACE/"
curl -s -o /dev/null -w "three  %{http_code}\n"           "$SPACE/vendor3d/three.module.min.js"
curl -s -o /dev/null -w "orbctl %{http_code}\n"           "$SPACE/vendor3d/OrbitControls.js"
curl -s "$SPACE/" | grep -c "MODELED — Orbital Roadmap"   # expect 1 (persistent banner)
curl -s "$SPACE/" | grep -c 'id="scene"'                  # expect 1 (render marker)
curl -s "$SPACE/" | grep -ci "http://\|cdn\."             # expect 0 external http CDN refs in markup
```

Then open `$SPACE/` in a browser: confirm the gold MODELED banner is pinned at the
top, the constellation renders (rotating globe + colored nodes + links), and the
governed-receipt panel populates (ground J/token `MEASURED`, orbital joules
`MODELED`, a `would-be signed receipt (MODELED — not a real signature)`).

If the live box is unreachable cross-origin, the page falls back to the baked
SAMPLE JSON and shows a `SAMPLE` badge — still MODELED, never fabricated.

## After publishing

- Report the final public URL back into `frontier/REPORT_DEV_4.md`.
- If the final slug differs from `szlholdings-orbital.hf.space`, update the link in:
  - `README.md` → "Orbital frontier showcase" section
  - `spaces/orbital/README.md` → showcase table
  - `artifacts/a11oy-uds/README.md` → ecosystem cross-reference
