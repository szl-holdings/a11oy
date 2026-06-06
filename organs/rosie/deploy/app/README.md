# rosie console app source — VENDORING REQUIRED (blocker)

This directory is intentionally a placeholder. The Zarf build (`deploy/Dockerfile`)
expects two files here that are **not yet in this repo**:

- `app.py` — the Gradio operator console (6 tabs: Span Explorer, Receipt Verifier,
  Mesh Health, Doctrine Sweep, Live Formulas, About). ~28.7 kB.
- `requirements.txt` — `gradio>=5.9.1`, `pydantic>=2.7.0`.

Both currently live **only** on the Hugging Face Space
[`SZLHOLDINGS/rosie-operator-console`](https://huggingface.co/spaces/SZLHOLDINGS/rosie-operator-console)
(HTTP 200, last verified 2026-05-30).

## To unblock the Zarf package build

Vendor the two files from the Space into this directory, with provenance:

```bash
curl -sSL https://huggingface.co/spaces/SZLHOLDINGS/rosie-operator-console/raw/main/app.py \
  -o deploy/app/app.py
curl -sSL https://huggingface.co/spaces/SZLHOLDINGS/rosie-operator-console/raw/main/requirements.txt \
  -o deploy/app/requirements.txt
```

Pin to a specific Space commit (not `main`) so the build is reproducible, and record
that commit SHA in the commit message. Until then, the `zarf-build-and-sign.yml`
image-build step will fail by design — see the PR body and
`zarf_real_audit/blockers.md`.

Why not just import the rosie library? Because the rosie git repo is a TypeScript /
Python **library** (`src/qec`, `src/replay`, `src/topology`, `khipu-receipt.ts`).
`package.json` `build` is `tsc --noEmit` — it produces no runnable artifact and there
is no `app.py` entrypoint in the repo.
