<!-- szl-investor-header -->
<div align="center">

# docs-site

### The unified documentation hub for everything SZL — quickstarts, how-to recipes, and the full technical reference for governed AI.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE) [![Build](https://github.com/szl-holdings/docs-site/actions/workflows/deploy-pages.yml/badge.svg?branch=main)](https://github.com/szl-holdings/docs-site/actions/workflows/deploy-pages.yml) [![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-Build_L2_(5_organ_images)-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels)

[Docs](https://docs.szlholdings.com) · [Quickstart](https://docs.szlholdings.com/quickstart) · [Live demo](https://docs.szlholdings.com) · [SZL Holdings](https://szlholdings.com)

</div>

## 💡 Why it matters

It is where investors, design partners, and engineers go to understand what SZL does, try it in minutes, and verify the claims for themselves — all in plain language with deep technical docs one click away.

## ▶️ Live demo

**[Open the live demo →](https://docs.szlholdings.com)**

[![demo screenshot](https://raw.githubusercontent.com/szl-holdings/szl-brand/main/kit/logos/png/kanchay-512.png)](https://docs.szlholdings.com)

<sub>_Screenshot: SZL Holdings kanchay mark — replace with a live capture of the running surface._</sub>

## ⚡ Quick start (30 seconds)

```bash
git clone https://github.com/szl-holdings/docs-site.git
cd docs-site
make quickstart   # or: see docs.szlholdings.com/quickstart
```

## 🔍 How it works

In two sentences: this component is part of SZL's governed-AI mesh — it enforces policy and emits signed, replayable audit receipts so every AI action can be verified after the fact. The full mathematical foundation, formal proofs, and protocol details are documented below and in the [technical docs](https://docs.szlholdings.com).

---

<details>
<summary><strong>📐 Full technical detail, math, and proofs (the proof, not the pitch)</strong></summary>

# SZL Holdings — Unified Documentation Site

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)
[![CI](https://github.com/szl-holdings/docs-site/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/docs-site/actions)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg)](SECURITY.md)


<!-- CII-BEST-PRACTICES-BADGE: PENDING — replace 'PENDING' with the project id once founder registers this repo at https://bestpractices.coreinfrastructure.org/ -->
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/PENDING/badge)](https://bestpractices.coreinfrastructure.org/)

The source for the SZL Holdings documentation portal (target: `docs.szlholdings.com`).
It documents the five flagships (a11oy, amaru, sentra, killinchu, rosie), the PURIQ
doctrine and master formula, the twelve anatomy organs plus the Killinchu bridge, the
Doctrine v11/v12 LOCKED contract numbers, the evidence ledger (DOIs, replay hash, Lean
artifacts), SDKs, API reference, cookbook, use cases, compliance, and brand.

---

## Why VitePress

The brief allowed VitePress, Docusaurus, or MkDocs Material. We chose **VitePress 1.6.x**.

| Requirement | How VitePress satisfies it |
| --- | --- |
| Dark + light mode | Built in to the default theme — no plugin, instant toggle, respects system preference. |
| Built-in search | Ships with local MiniSearch full-text indexing (no Algolia account, no external service, zero recurring cost). |
| KaTeX math | The PURIQ master formula and every organ sub-formula are LaTeX. We render them with `@vscode/markdown-it-katex` (a markdown-it plugin) — server-side at build time, so math is in the static HTML, fast and JS-light. |
| Mermaid diagrams | `vitepress-plugin-mermaid` integrates Mermaid into fenced ` ```mermaid ` blocks. Used for anatomy data-flow and DAG diagrams. |
| Copy-button + syntax highlighting | Built in (Shiki). Every code block gets a copy button and accurate highlighting with no configuration. |
| 3D iframes | Pages are plain markdown + HTML, so embedding the `*.static.hf.space` 3D showcases as `<iframe>` is trivial. |
| Fast static output, easy hosting | Vite-powered build emits a flat static bundle deployable to any static host (S3, the pplx.app preview, GitHub Pages, Cloudflare). |
| Lightweight | A Vue/Vite single-toolchain stack — far smaller dependency surface than Docusaurus (React + Webpack/Docusaurus core) and no Python runtime like MkDocs. Faster cold builds, simpler CI. |

Docusaurus was rejected as heavier than needed for a docs-only site (React app shell,
versioned-docs machinery we do not use). MkDocs Material was rejected because KaTeX +
Mermaid + Vue-style theming is less ergonomic and it adds a Python toolchain alongside the
Node tooling the rest of the SZL stack already uses.

---

## Toolchain pin & security review

VitePress 1.6.x natively depends on **Vite 5**, which in turn pulls **esbuild ≤ 0.24.2**.
That esbuild line carries [GHSA-67mh-4wv8-2f99](https://github.com/advisories/GHSA-67mh-4wv8-2f99)
(dev-server request-smuggling, moderate), and there is **no fix available through the
dependency chain** while we stay on VitePress 1.x. To keep `npm audit` clean we force a
maintained Vite + esbuild via the `overrides` block in `package.json`:

```jsonc
"overrides": {
  "vite": "^6.4.2",     // VitePress 1.x ships Vite 5; force a maintained line
  "esbuild": "^0.25.0"  // patches GHSA-67mh-4wv8-2f99
}
```

**Decision: keep the override (do not "upgrade off it") for now.** The audit evidence:

| Config | Resolved | `npm audit` |
| --- | --- | --- |
| No override (native VitePress 1.6.x) | vite 5.4.x + esbuild 0.21.x | **4 moderate** |
| esbuild-only override | vite 5.4.x + esbuild 0.25.x | **3 moderate** (audit still flags vite 5 itself) |
| **vite + esbuild override (current)** | vite 6.4.x + esbuild 0.25.x | **0 vulnerabilities** ✅ |

The natural "supported toolchain" upgrade — **VitePress 2.x**, which ships Vite 7 — is **not
viable yet**:

- VitePress 2.x is published only under the `next` dist-tag (`2.0.0-alpha.*`); there is no
  stable 2.x release for a production docs site.
- `vitepress-plugin-mermaid` (latest `2.0.17`) declares a peer dependency of
  `vitepress: ^1.0.0 || ^1.0.0-alpha` — it does **not** support VitePress 2.x, so a 2.x
  bump would break the Mermaid diagrams this site relies on.

**Exit criteria — remove/shrink the override when *both* are true:**

1. `npm view vitepress dist-tags.latest` is a stable `2.x` (no `-alpha`/`-beta`), **and**
2. `vitepress-plugin-mermaid` (or a replacement) supports VitePress 2.x in its peer deps.

When that happens, upgrade `vitepress` (and the mermaid plugin) and delete the `overrides`
block — VitePress 2.x's native Vite 7 / esbuild 0.25+ is already non-vulnerable.

This is re-checked automatically every month by
[`.github/workflows/docs-toolchain-review.yml`](../../.github/workflows/docs-toolchain-review.yml),
which runs `npm audit` against this site and reports whether the 2.x exit criteria are met.

---

## Project layout

```
szl_docs_site/
├── package.json                 # scripts + deps
├── docs/
│   ├── .vitepress/
│   │   ├── config.mjs           # nav, sidebar, search, KaTeX, Mermaid, fonts
│   │   ├── theme/
│   │   │   ├── index.js         # extends DefaultTheme
│   │   │   └── custom.css       # Kanchay brand tokens (navy/cyan/sand/clay/gold/ink)
│   │   └── dist/                # build output (generated — do not edit by hand)
│   ├── public/
│   │   └── img/                 # logo + 3d/ screenshots
│   ├── index.md                 # Home (hero, what is SZL, 5 flagships, CTAs)
│   ├── quickstart.md
│   ├── flagships/               # index + a11oy, amaru, sentra, killinchu, rosie
│   ├── anatomy/                 # index (12 organs + Killinchu bridge) + 3d-showcases
│   ├── doctrine/                # puriq (master formula), v11-v12 (LOCKED numbers)
│   ├── evidence/                # DOIs, replay hash, Lean, thesis, Khipu receipts
│   ├── sdks/                    # index + python + typescript
│   ├── api/                     # index + a11oy + killinchu (OpenAPI placeholders)
│   ├── cookbook/                # index + anatomy-evolved-v1
│   ├── use-cases/               # warhacker, greene-demo, iron-dome-brain, sovereign-gov
│   ├── compliance.md
│   ├── brand.md
│   ├── status.md
│   └── about.md
└── README.md                    # this file
```

---

## Develop & build

Prerequisites: Node 18+ and npm.

```bash
# install dependencies
npm install

# live dev server with hot reload (http://localhost:5173)
npm run docs:dev

# production build → docs/.vitepress/dist/
npm run docs:build

# preview the production build locally (http://localhost:4173)
npm run docs:preview
```

---

## How to update content

1. **Edit or add a page.** Pages are Markdown under `docs/`. Front-matter at the top of a
   file controls layout (e.g. `layout: home` on `index.md`).
2. **Add it to the sidebar/nav.** Edit `docs/.vitepress/config.mjs` — the `nav` array is the
   top bar, the `sidebar` object maps URL path prefixes to their link groups.
3. **Math:** write LaTeX inside `$ ... $` (inline) or `$$ ... $$` (block). KaTeX renders it
   at build time.
4. **Diagrams:** use a fenced ` ```mermaid ` block.
5. **Code:** standard fenced code blocks get syntax highlighting and a copy button
   automatically. Add a language hint (` ```python `, ` ```ts `, ` ```bash `).
6. **Images / screenshots:** drop files in `docs/public/img/` and reference them as
   `/img/yourfile.png` (the `public/` prefix is stripped at build).
7. **Brand colors** live as CSS custom properties in `docs/.vitepress/theme/custom.css`
   (Kanchay tokens). Adjust there to retheme globally.
8. Run `npm run docs:build`, eyeball with `npm run docs:preview`, then deploy.

### Editing the LOCKED contract numbers

The Doctrine v11 LOCKED numbers (749 declarations / 14 unique axioms / 163 sorries /
13-axis yuyay_v3 / replay hash `bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5`)
are quoted verbatim on `doctrine/v11-v12.md`, `evidence/index.md`, and the home page. These
are a frozen contract — do **not** change them to track live corpus growth. The live
snapshot (which drifts) is reported separately and labelled as such. If the doctrine is
re-locked at a new version, update all three pages together and bump the version label.

---

## Deploy & the relocatable-build design

The build emits a static bundle at `docs/.vitepress/dist/`. Two settings make that bundle
**fully relocatable** — it renders correctly no matter what path prefix it is served under,
including an unpredictable proxy sub-path (the `pplx.app` preview):

1. **`base: './'` + `mpa: true`** in `config.mjs`. MPA (multi-page app) mode disables
   VitePress's client-side SPA router, so every page is fully static HTML and there is no
   router that can 404 when the served path does not match a fixed `base`. The relative
   base makes every asset reference relative rather than rooted at `/`.
2. **`fix-relative-paths.mjs`** runs automatically after `vitepress build` (wired into the
   `docs:build` script). VitePress's `base: './'` emits `./asset` references that are only
   correct for root-level pages; this post-processor rewrites them to the correct
   `../`-depth for each nested page (e.g. `flagships/a11oy.html` gets `../assets/...`). The
   result is a bundle every page of which resolves its own assets relative to its own
   location.

This was a deliberate trade: MPA loses VitePress's instant in-page SPA navigation (each
nav click is a real page load), which is an acceptable cost for a documentation site that
must survive being served behind an opaque proxy.

- **Current preview host:** the Perplexity `deploy_website` flow uploads
  `docs/.vitepress/dist/` and serves it at a `pplx.app` proxy URL.
- **Production target:** `docs.szlholdings.com` at the domain root. Because the build is
  relocatable, it works at root as-is. If you prefer the lighter SPA experience at the
  production root, you may set `base: '/'`, `mpa: false`, `cleanUrls: true`, remove the
  `fix-relative-paths.mjs` step, and rebuild — the SPA build is correct when served from a
  known root.

---

## Source repository

`github.com/szl-holdings/docs-site`

---

Maintained by SZL Holdings. Content is the SZL doctrine of record; the LOCKED numbers are a
contract. NO BANDAID. Math-grounded, Quechua-rooted.

— Yachay

## SZL Holdings

![SZL Holdings](./branding/szl-avatar-animated.gif)

*Amaru — the Inca avatar of SZL Holdings. Animated mark (400×400, 16fps loop). Signed Yachay.*


</details>

<!-- szl-doctrine-footer -->

---

### Citation & doctrine

Cite this work via [`CITATION.cff`](CITATION.cff). Math foundations: [szl-papers](https://github.com/szl-holdings/szl-papers) · [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel `c7c0ba17`).

<sub>Λ Conjecture 1 (not a theorem) · 749/14/163 v11 LOCKED (kernel `c7c0ba17`) · SLSA Build L2 on all 5 organ images (L3 not claimed; bundle artifact not yet attested) · proved formulas = 5 {F1,F11,F12,F18,F19} · Section 889 = 5 vendors · [SZL Holdings](https://szlholdings.com) · Apache-2.0 code · CC-BY-4.0 papers</sub>

