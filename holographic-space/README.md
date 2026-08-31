---
title: a11oy Holographic Estate
emoji: ◇
colorFrom: gray
colorTo: green
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Signpost to the a11oy holographic estate at a-11-oy.com
---

<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
-->

# a11oy · Holographic Estate (standalone Space)

This Hugging Face **static** Space is a lightweight signpost that redirects to the canonical
a11oy holographic estate. The YAML front-matter above is the important part — a HF static Space
must declare `sdk: static` and an `app_file` that actually exists in the repo, or it serves
nothing and returns **404**. This Space serves [`index.html`](index.html), which:

- shows an honest one-screen landing (no overclaim), then
- redirects to the canonical estate at **https://a-11-oy.com/holographic** (via
  `<meta http-equiv="refresh">` for the no-JS path plus a `location.replace()` for browsers
  with JS), with a manual button as the final fallback.

## Why this exists

The live holographic estate — the Brain (live knowledge graph), the frontier surfaces, and the
public receipt verifier — is served by the main a11oy application at the canonical domain
`a-11-oy.com` (hyphenated; that is the only official a11oy home). Duplicating the full 3D estate
here would drift out of sync, so this Space intentionally stays a thin, honest redirect.

## Honest status

- **0 runtime CDN.** `index.html` is fully self-contained: inline CSS, system fonts, no external
  script or style fetch (Doctrine v11).
- **No fabricated claims.** locked-proven formulas = **8** `{F1,F4,F7,F11,F12,F18,F19,F22}`;
  Λ = **Conjecture 1** (advisory, never "proven"); Khipu BFT = Conjecture 2.
- **Canonical domain** is `a-11-oy.com`. `a11oy.net` is **not** us.

## Files

| File | Role |
|------|------|
| `README.md` | HF Space config (this front-matter) + docs |
| `index.html` | The static landing / canonical redirect (the `app_file`) |
| `PUBLISH.md` | Founder-only instructions to push these files to the `SZLHOLDINGS/holographic` Space |

## Publishing

Devs cannot push to the private `SZLHOLDINGS/holographic` Space. See [`PUBLISH.md`](PUBLISH.md)
for the exact founder steps to drop these two files (`README.md` + `index.html`) into the Space
and un-404 it.
