# Release Process

> Doctrine v11 LOCKED · 749/14/163 · locked_at `c7c0ba17`

This repo ships via `.github/workflows/release.yml` (OPS WAVE A, item 13).

## Flow

1. **Freeze source and metadata** — merge a test-clean commit to `main`; ensure
   `CITATION.cff`, `.zenodo.json`, `CHANGELOG.md`, package version, and release
   notes agree.
2. **Create the GitHub tag and release** — the current workflow is triggered by
   the GitHub `release.created` event. A push to `main` alone does **not** create
   a release.
3. **Attach evidence** — `.github/workflows/release.yml` generates a CycloneDX
   SBOM, GitHub build/SBOM attestations, Sigstore keyless DSSE receipt signatures,
   and uploads the resulting assets to the release.
4. **Archive through Zenodo** — when the repository's GitHub/Zenodo integration
   is enabled, Zenodo archives the immutable release and returns a version DOI.
   Read that DOI back from Zenodo and verify it resolves before adding it to the
   release identity. Never type or predict a DOI.
5. **Publish product links** — after DOI readback, update the version DOI on
   `a-11-oy.com`; `a11oy.net` remains a permanent redirect to the canonical
   domain.

## Verifying a release

```bash
cosign verify-blob \
  --certificate <artifact>.crt --signature <artifact>.sig \
  --certificate-identity-regexp 'https://github.com/szl-holdings/a11oy/.github/workflows/release.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  <artifact>
```

## Permissions note

Requires `id-token: write` (already set in the workflow). If releases fail to create PRs/tags,
the org may need: Settings → Actions → General → Workflow permissions → read+write.

Co-Authored-By: Perplexity Computer Agent
