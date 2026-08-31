<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
-->

# PUBLISH — un-404 the `SZLHOLDINGS/holographic` Space (founder-only)

The private Space **`SZLHOLDINGS/holographic`** currently returns **404**: it is a static SDK
Space whose repo does not serve a valid `app_file`. This directory contains a correct drop-in
fix. Devs cannot push to that Space — **only the founder can**. These are the exact steps.

## What to push

Only two files, both from this `holographic-space/` directory:

- `README.md`  → becomes the Space's `README.md` (its `sdk: static` + `app_file: index.html`
  front-matter is what makes HF serve the page instead of 404)
- `index.html` → the landing / canonical redirect (the declared `app_file`)

> Do **not** copy `PUBLISH.md` into the Space — it is a repo-side instruction file, not part of
> the served site. Do not add secrets; a static Space needs none.

## Why it 404s today

A HF **static** Space serves files straight from the repo root. It returns 404 / a blank page
when either:
1. the `README.md` YAML front-matter is missing / wrong (no `sdk: static`, or an `app_file`
   that does not exist in the repo), or
2. there is no `index.html` at the repo root to serve.

The `README.md` in this directory fixes (1) and `index.html` fixes (2).

## Option A — web UI (simplest, no tokens)

1. Go to `https://huggingface.co/spaces/SZLHOLDINGS/holographic` → **Files** tab.
2. Confirm Space **Settings → SDK = Static**. (If a different SDK is set, switch it to *Static*.)
3. **Add file → Upload files** (or **Create/Edit file**):
   - upload / paste `index.html` (contents from `holographic-space/index.html`),
   - edit `README.md` so its top matches `holographic-space/README.md` (the `sdk: static` +
     `app_file: index.html` front-matter block is the load-bearing part).
4. Commit to `main`. The Space rebuilds; the 404 clears within a minute.
5. Verify: open `https://huggingface.co/spaces/SZLHOLDINGS/holographic` — it should show the
   signpost and redirect to `https://a-11-oy.com/holographic`.

## Option B — git push (from the founder's machine)

```bash
# 1. Clone the Space repo (needs a HF write token for the private Space).
git clone https://huggingface.co/spaces/SZLHOLDINGS/holographic hf-holographic
cd hf-holographic

# 2. Copy the two drop-in files from the a11oy checkout.
#    (adjust the path to wherever you cloned szl-holdings/a11oy)
cp /path/to/a11oy/holographic-space/index.html ./index.html
cp /path/to/a11oy/holographic-space/README.md  ./README.md

# 3. Commit + push to the Space's main branch.
git add index.html README.md
git commit -m "fix: serve static landing (sdk: static, app_file: index.html) — un-404"
git push
```

If `git push` asks for credentials, use your HF username + a **write** access token
(`https://huggingface.co/settings/tokens`), not your account password.

## Verify it worked

- `https://huggingface.co/spaces/SZLHOLDINGS/holographic` no longer 404s and shows the ◇ landing.
- Within ~2s it redirects to `https://a-11-oy.com/holographic` (or the button does it manually).
- Space **Settings → SDK** reads *Static*; **build logs** show a successful static build.

## Notes / doctrine

- Canonical domain is **`a-11-oy.com`** (hyphenated). `a11oy.net` is not us — do not point there.
- The page is **0 runtime CDN** (inline CSS, system fonts, no external fetch) — keep it that way.
- No secrets are needed for a static Space. **Never** add a token or key to the Space repo.
- This is intentionally a thin redirect so it can never drift out of sync with the real estate.
