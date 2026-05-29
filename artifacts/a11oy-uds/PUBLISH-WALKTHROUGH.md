# Publishing the first A11oy UDS release

Step-by-step to take the publish pipeline from "committed to the repo" to
"`zarf package pull oci://ghcr.io/szl-holdings/a11oy-uds:0.1.0` works."

All commands run from the repo root unless noted.

## 0. Pre-flight (one-time)

Per `STANDBY-WALKTHROUGH.md`, the GitHub `origin` for
`github.com/szl-holdings/platform` is **behind by ~1,598 commits**
and **push is blocked** because the OAuth token attached to `origin` lacks the
`workflow` scope. That blocks the new `.github/workflows/a11oy-uds-publish.yml`
file from reaching GitHub.

Resolve once:

```bash
# 1. Create a PAT at https://github.com/settings/tokens with: repo + workflow scopes.
# 2. Point origin at it (use HTTPS, not SSH, so the PAT is honored):
git remote set-url origin https://<github-user>:<PAT>@github.com/szl-holdings/platform.git

# 3. Reconcile the divergence.
git fetch origin
git merge origin/master
#   Conflicts expected in package.json files and pnpm-lock.yaml from the
#   Dependabot tanstack bump on the remote. Per STANDBY-WALKTHROUGH.md,
#   keep the Dependabot version bumps; resolve other conflicts in favor of HEAD.
pnpm install   # rebuild lockfile if needed

# 4. Sanity-check the working tree.
pnpm --filter @workspace/a11oy-uds run build
#   Expected (on a host without zarf): a fallback tarball at
#   dist/a11oy-uds-fallback/a11oy-uds-0.1.0.fallback.tar.zst.
#   On GitHub Actions, zarf is installed by the workflow and the real
#   Zarf package lands in dist/a11oy-uds/ instead.
```

## 1. Push the workflow file so it exists on GitHub

```bash
git push origin master
```

Verify:

- Visit https://github.com/szl-holdings/platform/actions and
  confirm **"Publish A11oy UDS payload"** appears in the left sidebar.
- The first push to `master` that touches `artifacts/a11oy-uds/**` will
  automatically trigger the **dev** channel run.

## 2. Dry-run the dev channel before cutting a tag

Quickest way to prove the workflow goes green without committing to a real
version number: trigger the workflow by hand on the dev channel.

```
GitHub UI: Actions -> Publish A11oy UDS payload -> Run workflow
  Branch: master
  channel: dev
```

Expected on success:

- Job summary shows
  `Published ref: ghcr.io/szl-holdings/a11oy-uds:0.1.0-multi`
  and
  `Primary tag: ghcr.io/szl-holdings/a11oy-uds:dev-<sha>`.
- Package appears at
  https://github.com/orgs/szl-holdings/packages?repo_name=platform
  as `a11oy-uds`.
- The package will be **Private by default**. To let Andrew pull without auth,
  open the package -> *Package settings* -> *Change visibility* -> **Public**.
  (Optional: scope it to the org and the published Actions workflow under
  *Manage Actions access* so only this workflow can publish.)

Smoke-test the pull from any machine with `zarf`:

```bash
zarf package pull oci://ghcr.io/szl-holdings/a11oy-uds:dev
zarf package inspect zarf-package-a11oy-uds-*.tar.zst
```

If either step fails, fix on `master` and re-run the dev workflow. Do **not**
cut the tag in step 3 until the dev channel publishes cleanly.

## 3. Cut the first release tag

```bash
# Confirm package.json version is what you want to ship (currently 0.1.0).
node -p "require('./artifacts/a11oy-uds/package.json').version"

# Tag and push. The publish workflow triggers on v*.*.* tags.
git tag -a v0.1.0 -m "a11oy-uds v0.1.0 — first signed release"
git push origin v0.1.0
```

The workflow will:

1. Build the payload.
2. Push to `ghcr.io/szl-holdings/a11oy-uds:0.1.0-multi`.
3. Re-tag to `:0.1.0` and `:latest`.
4. **Cosign keyless-sign** the published digest (uses GitHub's OIDC issuer; no
   secret to manage).
5. Attach the `*.tar.zst`, `*.sig`, and `*.sha256` files to the GitHub Release
   for `v0.1.0`.

## 4. Verify the release before sending the email

```bash
# 4a. Pull works by name + version:
zarf package pull oci://ghcr.io/szl-holdings/a11oy-uds:0.1.0
zarf package inspect zarf-package-a11oy-uds-*.tar.zst

# 4b. Signature verifies against the workflow identity:
cosign verify \
  --certificate-identity-regexp 'https://github.com/szl-holdings/platform/\.github/workflows/a11oy-uds-publish\.yml@.+' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/szl-holdings/a11oy-uds:0.1.0
```

Both should succeed. If `cosign verify` fails, the certificate-identity-regexp
is the most likely culprit — match it exactly against what the run produced
(visible in the Actions log for the `Sign published payload` step).

## 5. Capture the three links you'll send Andrew

After step 4 passes, grab and paste these into the email:

- **Actions run URL** for the `v0.1.0` workflow run
  (`https://github.com/szl-holdings/platform/actions/runs/<id>`).
- **Package URL** on GHCR
  (`https://github.com/orgs/szl-holdings/packages/container/package/a11oy-uds`).
- **Release URL** with attached `.tar.zst` / `.sig` / `.sha256`
  (`https://github.com/szl-holdings/platform/releases/tag/v0.1.0`).

## Rollback / re-cut

If `v0.1.0` ships broken:

```bash
# Delete the local + remote tag.
git tag -d v0.1.0
git push origin :refs/tags/v0.1.0

# Delete the GitHub Release (UI: Releases -> v0.1.0 -> Delete).
# Optionally untag :latest on GHCR (Package settings -> Manage versions).

# Fix on master, then re-cut.
git tag -a v0.1.0 -m "..."
git push origin v0.1.0
```

Pulling by **digest** (e.g. `ghcr.io/szl-holdings/a11oy-uds@sha256:...`) is
always immutable even when tags move. The Actions summary prints the digest
for every run.

## Known sharp edges

- **Lockfile drift.** `pnpm install --frozen-lockfile` in the workflow will
  fail if `pnpm-lock.yaml` is out of date. Run `pnpm install` locally and
  commit any lockfile changes before pushing.
- **Architecture in zarf.yaml.** The published OCI tag is
  `<version>-<architecture>`, where `architecture` is read from
  `artifacts/a11oy-uds/zarf.yaml` (currently `multi`). If that value changes,
  the workflow's re-tag step will automatically follow it; no workflow edit
  needed.
- **Package visibility.** New GHCR packages default to private. Until you flip
  it to public after the first publish, `zarf package pull` from outside the
  org will return 401.
