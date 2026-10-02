# Brand Kit

SZL's brand is itself an [organ](/anatomy/#kanchay): **Kanchay** (Quechua *kanchay* =
"light / radiance"), the public-claim surface. The brand is governed by the same honesty axes as
everything else — a public claim ships only if it clears the two sacred axes
(`moralGrounding ≥ 0.95 ∧ measurabilityHonesty ≥ 0.95`).

## Brand kit repository

The authoritative brand assets (the orbit logo suite, social-preview templates (1280×640 PNG),
motion specs and visual-identity doctrine) live in
[**`szl-holdings/szl-brand`**](https://github.com/szl-holdings/szl-brand) (license **CC BY 4.0**).
[`kit/`](https://github.com/szl-holdings/szl-brand/tree/main/kit) is the source of truth, and
[`kanchay/`](https://github.com/szl-holdings/szl-brand/tree/main/kanchay) is the ready-to-vendor
bundle that surfaces copy from. It also ships a Python SDK for programmatic brand-asset generation.

## Color (KANCHAY)

This site runs on **SZL KANCHAY 1.1.1**, the founder-approved design system. The tokens are
defined in [`kit/tokens/szl-design-system.css`](https://github.com/szl-holdings/szl-brand/blob/main/kit/tokens/szl-design-system.css)
in `szl-brand`. The docs vendor the [`kanchay/`](https://github.com/szl-holdings/szl-brand/tree/main/kanchay)
bundle 1.1.1 (`szl-brand` main @ `83f852c`) byte for byte at `docs/public/szl/`:
`szl-design-system.css`, the orbit logos this site uses, and `SOURCE.json`, which pins the sha256
of every file. The design system loads before the theme. Vendored files are never edited here: a
token changes in `kit/`, the bundle is rebuilt, and it is copied in again.

KANCHAY names **roles**, not hex values, and ships **two surfaces from one token set**. The dark
operator surface is the default (`:root`), and these docs live on it. The light surface
(`[data-surface="light"]`) flips the same roles to their light values. VitePress's light mode sets
`data-surface="light"`, so both modes read the vendored values exactly. Code blocks stay dark on
both surfaces.

| Role | Tokens | On this site |
|------|--------|--------------|
| Space navy and neutrals | `--bg`, `--bg-deep`, `--surface`, `--surface-alt`, `--surface-raised`, `--border`, `--text`, `--text-sub`, `--text-ghost` | Page ground; sidebar and code wells; cards, tables and chips; all text |
| One coral node | `--accent`, `--accent-hover`, `--accent-press`, `--accent-ink` | The home page's primary action and the active-nav marker, one per view |
| Silver linework | `--hairline`, `--color-silver-*` | The orbit in the logo and hairline dividers, never text |
| Teal | `--link`, `--link-hover`, `--focus` | Links and the focus ring only |
| Gold | `--premium` | Premium or investor emphasis only, never a second accent |
| Red | `--color-error` | Errors and destructive actions only |
| Status | `--color-success`, `--color-warning`, `--color-error` | Status dots and warning or danger callouts, always paired with a word |

- **Mostly neutral.** A view has at most one coral moment. On the home page it is the primary
  action, so the active "Home" item carries no marker there.
- **Focus is a solid ring**: a 2px `--focus` outline, offset 2px, on every link, button and field.
- **Status is never color alone.** Every dot and callout carries a word.
- **Contrast.** Each text pair this theme sets was checked at WCAG AA on both surfaces: 4.5:1 for
  text, and 3:1 for marks, focus rings and control edges. The scale pairs are covered by
  [`COLOR_CONTRAST_REPORT.md`](https://github.com/szl-holdings/szl-brand/blob/main/kit/tokens/COLOR_CONTRAST_REPORT.md).

## Typography

No webfonts and no font CDN. KANCHAY uses the device's own font stacks, so text renders offline
on any OS without downloading anything.

| Token | Stack | Role |
|-------|-------|------|
| `--font-display` | `system-ui`, then the platform sans | Headings at weight 600–700, tracked `--tracking-tight` (−0.011em) |
| `--font-body` | `system-ui`, then the platform sans | Body copy: a 16px floor, line height 1.6 and a readable measure |
| `--font-mono` | `ui-monospace`, then the platform's developer mono | Code, hashes, receipt roots, counts and IDs, with tabular lining figures |

Mono carries audit data because `0`/`O` and `1`/`l`/`I` must never be confused. The type scale is
a Major Third (1.25) on a 16px base. KaTeX emits native MathML; the browser uses installed system math fonts.

## Logo

The SZL mark is the orbit: a silver ellipse tilted −22°, one coral node, and a small Λ on the
lower arc. The orbit is the receipt chain, the node is one claim on it, and the Λ-Spine is drawn
small because Conjecture 1 is open.

- **Use the suite's files; never redraw or recolor them.** The suite lives in
  [`kit/logos/`](https://github.com/szl-holdings/szl-brand/tree/main/kit/logos) and ships in the
  `kanchay/` bundle. The navbar uses the text title so it stays neutral. This site uses
  `szl_favicon_square.svg` in the browser tab, and `szl_favicon_32.png` and
  `szl_favicon_180.png` as icons. The home hero uses the one-color `szl_logo_mono_white.svg`
  (dark) and `szl_logo_mono_navy.svg` (light), because the hero's primary action is that view's
  one coral moment.
- **Clear space** equals the cap height of the "S" on every side. The full logo is never narrower
  than 120px, and the mark alone never smaller than 24px.
- **Rules:** [`LOGO_USAGE.md`](https://github.com/szl-holdings/szl-brand/blob/main/kit/logos/LOGO_USAGE.md).
  The lattice mark and the gold wordmark are retired.

## Usage rules

- **No mysticism.** Brand language is etymological and mathematical, never ritual.
- **No overclaim.** "SLSA L3", "zero sorry", and unscoped "fully verified" are banned claims.
- **Attribution:** CC BY 4.0 — credit SZL Holdings, ORCID
  [0009-0001-0110-4173](https://orcid.org/0009-0001-0110-4173).
