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

This site runs on **SZL Kanchay v1.0.0**, the shipped design-token export. Its source is the
`kanchay/` folder of [`szl-holdings/szl-brand`](https://github.com/szl-holdings/szl-brand):
`tokens.json` is the source of truth and `kanchay.css` is generated from it. The docs vendor
the export byte for byte at `docs/public/kanchay/` (`kanchay.css`, three font files, the
marks, and `SOURCE.json` with the sha256 of every file) and load it before the theme. The
vendored files are never edited here: a token changes in `szl-brand`, then the export is
copied in again.

Kanchay names **roles**, not hex values. Dark is home: the dark values sit on `:root`, and
the light theme maps the same roles onto the gray scale under `[data-theme="light"]`. This
site mirrors VitePress's dark/light switch onto `data-theme`, so both themes read the
exported values exactly.

| Role | Tokens | On this site |
|------|--------|--------------|
| Ground and depth | `--color-a11oy-bg`, `-deep`, `-surface`, `-overlay` | Page; sidebar; cards, tables and code; hover and pressed fills |
| Text | `--color-a11oy-text`, `-text-sub`, `-text-ghost` | Body and headings; secondary copy; metadata |
| Accent (gold) | `--color-a11oy-gold`, `--gold-bright`, `--color-on-accent` | The primary button, the active nav item, card titles; hover; the label on a gold fill |
| Proof (teal) | `--color-ink-signal`, `--color-focus`, `--teal` | Links, inline code and locked contract numbers; focus rings; tip callouts |
| Status | `--color-success`, `-warning`, `-error`, `-info`; `--color-ink-caution`, `--color-ink-danger` | Status dots and callouts, always paired with a word |
| Edges | `--color-a11oy-border-subtle`, `--color-a11oy-border`, `--color-control-border` | Card and code edges; region dividers; input edges |

- **Gold is the only accent**, and it fills one control per view.
- **Teal is proof**: links, hashes and verified values, never decoration.
- **Status is never color alone**: every dot or callout carries a word.
- **The mark** is `marks/szl-mark-gold.svg` on dark and `marks/szl-mark-ink.svg` on light.

Each text pair this theme introduces was checked at WCAG AA (4.5:1 for text, 3:1 for focus
rings and marks) in both themes when the site moved onto the export.

## Typography

Three faces, each shipped as a local file in the export (`kanchay/fonts/`). No font CDN.

| Face | Token | Role |
|------|-------|------|
| **Space Grotesk** | `--font-display` | Headlines: page titles and the home headline at weight 300, section headings at 600 |
| **Inter** | `--font-sans` | Everything people read and operate: body copy, navigation, tables |
| **JetBrains Mono** | `--font-mono` | Code, hashes, receipts, API paths and the locked contract numbers |

Headlines are tracked tight (−0.02 to −0.035em), mono labels are uppercase and tracked, and
columns of digits use tabular figures. The pairing keeps prose neutral and legible and gives
the formulas and receipts that carry the actual claims a precise monospace.

## Usage rules

- **No mysticism.** Brand language is etymological and mathematical, never ritual.
- **No overclaim.** "SLSA L3", "zero sorry", and unscoped "fully verified" are banned claims.
- **Attribution:** CC BY 4.0 — credit SZL Holdings, ORCID
  [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173).
