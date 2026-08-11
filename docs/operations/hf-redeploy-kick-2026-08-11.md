# Canonical A11oy redeploy kick — 2026-08-11

This source-only operations marker intentionally advances protected `main` so the existing `Sync and Relock Canonical Hugging Face Space` push controller can execute with repository-native `GITHUB_TOKEN` authority.

Reason: the organization-level recovery controller reached its exact protected source target but its legacy cross-repository `SZL_GITHUB_TOKEN` failed authentication with HTTP 401. The canonical A11oy workflow already runs on every protected-main push and owns the Hugging Face deployment, source binding, runtime configuration, readiness probe, relock, and strict post-deployment parity chain.

This marker changes no application code, model, dataset, secret, runtime configuration, hardware allocation, branch protection, ruleset, or Hugging Face state by itself. Deployment truth is established only by the resulting protected `hf-sync.yml` run and its persisted relock evidence.
