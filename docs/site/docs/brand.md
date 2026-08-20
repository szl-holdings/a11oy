# Brand Kit

SZL's brand is itself an [organ](/anatomy/#kanchay): **Kanchay** (Quechua *kanchay* =
"light / radiance"), the public-claim surface. The brand is governed by the same honesty axes as
everything else — a public claim ships only if it clears the two sacred axes
(`moralGrounding ≥ 0.95 ∧ measurabilityHonesty ≥ 0.95`).

## Brand kit repository

The authoritative brand assets — logo monograms, social-preview templates (1280×640 PNG), motion
specs, and visual-identity doctrine — live in
[**`szl-holdings/szl-brand`**](https://github.com/szl-holdings/szl-brand) (license **CC BY 4.0**).
It also ships a Python SDK for programmatic brand-asset generation.

::: info brand-kit repo
The task references a dedicated `szl-holdings/brand-kit` repository. Today the canonical brand
source is [`szl-holdings/szl-brand`](https://github.com/szl-holdings/szl-brand); a `brand-kit`
mirror/rename is **in development**. This page links to `szl-brand` as the live source and will
repoint when `brand-kit` publishes.
:::

## Color tokens (Kanchay)

The formal **Kanchay token export** (named CSS/JSON design tokens) is **in development** in
`szl-brand`. Until it publishes, this docs site uses the **live SZL brand palette** as the
placeholder token set — the same values used across every repo README and social preview:

| Token (placeholder) | Hex | Use |
|---------------------|-----|-----|
| `--szl-navy` | `#0B1F3A` | Primary brand / dark surfaces |
| `--szl-cyan-bright` | `#00D4FF` | Brand accent (on dark) |
| `--szl-cyan` | `#0094C6` | Accessible accent (on light) |
| `--szl-sand` | `#F5F1E8` | Warm light surface |
| `--szl-clay` | `#B9482F` | Warm accent |
| `--szl-gold` | `#B08940` | Etymology / highlight rule |
| `--szl-ink` | `#141413` | Body text (light) |

When the named Kanchay tokens publish, this site's
[`custom.css`](https://github.com/szl-holdings/docs-site/blob/main/docs/.vitepress/theme/custom.css)
will swap the placeholders for the canonical token names — a one-file change.

## Typography

- **Body:** **Inter** (400–800).
- **Mono / code:** **JetBrains Mono** (400–700).

Both are loaded from Google Fonts in the site head. This pairing is the SZL doctrine default:
a neutral, high-legibility grotesque for prose and a precise monospace for the formulas and
receipts that carry the actual claims.

## Usage rules

- **No mysticism.** Brand language is etymological and mathematical, never ritual.
- **No overclaim.** "SLSA L3", "zero sorry", and unscoped "fully verified" are banned claims.
- **Attribution:** CC BY 4.0 — credit SZL Holdings, ORCID
  [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173).
