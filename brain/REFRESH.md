<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
-->

# `brain/REFRESH.md` — daily self-refresh (DESIGN ONLY)

> **Status: MODELED / design-only.** This document describes how a daily refresh
> *would* re-run the harvest so the vault re-files itself. **No cron, workflow, or
> scheduler is created by this PR.** Wiring the schedule is a separate, explicit
> step for the operator (the main agent), so nothing runs unattended by surprise.

## Goal

Keep `brain/vault/` current as the estate changes: new frontier surfaces, new
formulas, repos added/archived, new workspace knowledge docs. The harvest is
idempotent — re-running it overwrites the derived notes and regenerates the
morning digest for the day.

## The one command

```bash
python3 brain/harvest_vault.py
```

That is the whole refresh. It is a pure read of the estate; it writes only under
`brain/vault/` and signs nothing.

## Design A — GitHub Actions (recommended when wired)

A scheduled workflow (illustrative — **not** added here):

```yaml
# .github/workflows/brain-refresh.yml   (DESIGN ONLY — do not commit without sign-off)
on:
  schedule:
    - cron: "17 6 * * *"     # 06:17 UTC daily (off the :00 mark)
  workflow_dispatch:
permissions:
  contents: write
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install fastapi
      - run: python3 brain/harvest_vault.py
      - name: Commit re-filed vault
        run: |
          git config user.name  "szl-brain-bot"
          git config user.email "stephenlutar2@gmail.com"
          git add brain/vault
          git diff --cached --quiet || git commit \
            -s -m "chore(brain): daily vault refresh $(date -u +%F)"
          git push
```

Notes:
- Off-peak minute (`17`), not `:00`, so the org's scheduled jobs don't all fire
  at once.
- `-s` keeps the DCO sign-off on the auto-commit (Doctrine v11).
- `contents: write` is the only elevated scope; no secrets are needed — the
  harvest reads local files and baked-in snapshots, not the live GitHub API.

## Design B — host cron (self-hosted)

```cron
# 06:17 daily — re-file the vault, commit if changed
17 6 * * *  cd /srv/a11oy && python3 brain/harvest_vault.py && \
            git add brain/vault && \
            git diff --cached --quiet || git commit -s -m "chore(brain): daily vault refresh" && \
            git push
```

## Keeping the repo snapshot honest

The 34-repo list in `a11oy_brain_graph.ORG_REPOS_SNAPSHOT` is a **static** snapshot
(captured `2026-07-07`) so the endpoint is a pure read with no runtime network
call. A future refresh step may re-capture it:

```bash
gh repo list szl-holdings --no-archived --json name --jq 'sort_by(.name)[].name'
```

and update the snapshot list + `captured` date in `a11oy_brain_graph.py`. Until
that is wired, the snapshot is labeled MODELED and dated, so its provenance is
honest.

## What refresh does NOT do

- It does not sign anything (a harvest is a read; receipts belong on writes).
- It does not call the live GitHub API at request time.
- It does not fabricate counts — if a source is missing, that source is reported
  as empty/absent, never padded.
