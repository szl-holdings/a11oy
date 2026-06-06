<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7 -->

# `@szl-holdings/rosie-widget`

The ambient operator widget for the SZL stack. A floating launcher, a `⌘K` /
`Ctrl-K` command palette, and execute-with-confirm — present in every SZL
application rather than a page you navigate to.

You do not open a console; the assistant is already there. Click the floating
button (or press `⌘K` / `Ctrl-K`), ask a question, and the panel answers
scoped to the current app. Ask it to do something consequential and it shows a
human-confirm dialog with the signed receipt preview before anything runs.

---

## What it is

`<rosie-widget>` is a single framework-agnostic custom element built with
[Lit](https://lit.dev/). It renders entirely inside Shadow DOM, carries one
runtime dependency (Lit), and ships as a < 30 KB gzipped bundle. It is:

- **Floating** — an always-visible circular launcher, bottom-right by default.
- **Keyboard-first** — `⌘K` / `Ctrl-K` opens a fuzzy command palette inside the
  same panel; `Esc` collapses it back to the button.
- **Conversational** — a chat thread with receipt cards rendered inline.
- **Consequential-safe** — a confirm dialog gates every execute action and
  shows the signed receipt preview before signing.

---

## The five hosts it embeds in

| Host      | Accent       | Surface                                   |
| --------- | ------------ | ----------------------------------------- |
| a11oy     | cyan `#00d4ff`     | Governed execution fabric web UI    |
| amaru     | gold `#f5b32a`     | Receipt-minting cortex web UI       |
| sentra    | green `#3ddc84`    | Sanctions / dark-vessel detection UI |
| vessels   | ocean-cyan `#0099cc` | Maritime investor-demo UI        |
| rosie     | coral `#ff7a59`    | Standalone console (embedded case)  |

The `app` attribute selects the receipt filter and the accent.

---

## Relationship to the standalone Gradio console

This widget does **not** replace the
[`rosie-operator-console`](https://huggingface.co/spaces/SZLHOLDINGS/rosie-operator-console)
Gradio Space. The two are complementary:

| | **rosie-operator-console** (Gradio Space) | **rosie-widget** (this widget) |
| --- | --- | --- |
| Role | Admin / forensics console | Ambient daily-use surface |
| Surface | Full standalone app, 6 tabs (Span Explorer, Receipt Verifier, Mesh Health, Doctrine Sweep, Live Formulas, About) | Floating button + slide-in panel inside each app |
| Scope | Unrestricted, all apps | Filtered to the hosting app |
| When | Deep investigation, replay, audit | In-context questions and confirmed actions |

The console stays the place an operator goes for forensic depth; the widget is
where day-to-day questions and confirmed actions happen, without leaving the
app you are already in.

---

## Quick start (host)

```html
<script
  type="module"
  src="https://cdn.szlholdings.com/rosie-widget/v0.3.1/rosie-widget.js"
></script>
<rosie-widget app="a11oy" api-base="/api/rosie"></rosie-widget>
```

or

```typescript
import '@szl-holdings/rosie-widget';
// <rosie-widget app="a11oy" api-base="/api/rosie" />
```

Full contract, attributes, CSS variables, and the rosie-api endpoint list are
in [`docs/HOST_INTEGRATION.md`](./docs/HOST_INTEGRATION.md).

---

## Develop locally

```bash
cd packages/widget
npm install
npm run dev          # Vite serves index.html with a live <rosie-widget>
npm run build        # ESM + UMD bundles into dist/
npm run size         # check the gzipped bundle stays under 30 kB
npm run storybook    # four visual stories on http://localhost:6007
```

The demo page (`index.html`) lets you switch the host app to preview all five
accents. With no live rosie-api the widget shows its offline message and makes
no network calls.

---

## Themes

One accent per host, applied via the `--rosie-accent` custom property and
derived automatically from `app`:

- a11oy → cyan
- amaru → gold
- sentra → green
- vessels → ocean-cyan
- rosie → coral

A host can override with the `theme` attribute or by setting `--rosie-accent`
in its own stylesheet.

---

## The substrate relationship

The widget is the **client** of the receipt substrate. It imports
`OperationalReceipt` and `VerifyResult` **type-only** from
`@szl-holdings/a11oy-receipt-substrate`; those imports are erased at build time,
so the widget bundle never carries the substrate runtime and does not require
the substrate to be published before the widget can build. A vendored ambient
declaration (`src/types/a11oy-receipt-substrate.d.ts`) keeps `tsc` and editors
happy until the real package is installed, at which point it transparently
shadows the shim.

---

(c) 2024–2026 SZL Holdings, LLC. Apache-2.0.
