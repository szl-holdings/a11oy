# Release Process

> Doctrine v11 LOCKED · 749/14/163 · locked_at `c7c0ba17`

This repo ships via `.github/workflows/release.yml` (OPS WAVE A, item 13).

## Flow (on push to `main`)

1. **Version bump** — simple monotonic counter `v0.1.N` (next-tag computed from existing tags).
2. **Tag + GitHub Release** — created via `softprops/action-gh-release`, auto-generated notes.
3. **Sign artifacts** — `cosign sign-blob` keyless (GitHub OIDC); `.sig` + `.crt` attached to the release.
4. **SLSA L1 provenance** — `slsa-framework/slsa-github-generator` generic generator emits
   `provenance-<tag>.intoto.jsonl` attached to the release.

## Verifying a release

```bash
cosign verify-blob \
  --certificate <artifact>.crt --signature <artifact>.sig \
  --certificate-identity-regexp 'https://github.com/szl-holdings/rosie/.github/workflows/release.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  <artifact>
```

## Permissions note

Requires `id-token: write` (already set in the workflow). If releases fail to create PRs/tags,
the org may need: Settings → Actions → General → Workflow permissions → read+write.

Co-Authored-By: Perplexity Computer Agent