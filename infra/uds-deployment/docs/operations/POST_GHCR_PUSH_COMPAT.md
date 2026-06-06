# Post-GHCR-push UDS Compat Plan

**Status:** STAGED — DO NOT MERGE until all 5 images live on ghcr.io/szl-holdings.

## When to merge

After the founder (or CI) successfully publishes:
- ghcr.io/szl-holdings/a11oy:uds-v0.3.1 (blocked on Dockerfile GID fix → vessels#175)
- ghcr.io/szl-holdings/amaru:uds-v0.3.1
- ghcr.io/szl-holdings/sentra:uds-v0.3.1 (blocked on sentra needing a Dockerfile)
- ghcr.io/szl-holdings/vessels:uds-v0.3.1 (currently has -vessels suffix only)
- ghcr.io/szl-holdings/rosie:uds-v0.3.1

AND each package's visibility is set to Public via GitHub UI.

## What this PR will remove

- STAGED-ADVISORY comments in zarf.yaml files
- Commented-out enabled: true entries in uds-bundle.yaml
- The verify-signed-assets.yml fallback to echo-only mode

See ghcr_readiness/STEPHEN_GHCR_PUSH.md in the audit workspace for the full
12-command sequence to publish all 5 images.

Authored-by: Perplexity Computer Agent
On-behalf-of: Stephen P. Lutar Jr. (founder authorized in session 2026-05-31)
