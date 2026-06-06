<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- © 2026 Lutar, Stephen P. — SZL Holdings — Doctrine v7 -->

# Host integration contract — `<rosie-widget>`

This document is the contract each host application (a11oy, amaru, sentra,
vessels) and the standalone rosie console follow to embed the ambient operator
widget. The widget is a single custom element. It carries no host framework
assumptions and runs the same way inside React, Gradio, an iframe, or plain
HTML.

---

## 1. Two ways to embed

### A. Script tag (CDN) — no build step

```html
<!-- in a11oy's web/index.html -->
<script
  type="module"
  src="https://cdn.szlholdings.com/rosie-widget/v0.3.1/rosie-widget.js"
></script>
<rosie-widget app="a11oy" api-base="/api/rosie"></rosie-widget>
```

The ESM bundle bundles Lit, so nothing else is required. The element registers
itself on import as a side effect (`customElements.define('rosie-widget', …)`).

### B. npm import — bundled by the host

```typescript
// in a11oy's web/src/main.tsx
import '@szl-holdings/rosie-widget';
```

```tsx
// then in JSX (React treats unknown lowercase tags as custom elements):
<rosie-widget app="a11oy" api-base="/api/rosie" />
```

> React note: pass `app` / `api-base` as **string attributes** (they are
> reflected primitives), not as React props. For the optional `token`, set it
> imperatively on the element ref to avoid leaking it into server-rendered
> markup.

---

## 2. Attributes

| Attribute  | Required | Default          | Meaning                                                                 |
| ---------- | -------- | ---------------- | ----------------------------------------------------------------------- |
| `app`      | yes      | `rosie`          | `a11oy` \| `amaru` \| `sentra` \| `vessels` \| `rosie`. Receipt filter + accent. |
| `api-base` | yes\*    | _empty_          | rosie-api URL. Empty → widget shows a "configure api-base" message and makes **no** network calls. |
| `position` | no       | `bottom-right`   | `bottom-right` \| `bottom-left`.                                        |
| `theme`    | no       | derived from app | Accent color override (any CSS color).                                  |
| `token`    | no       | _empty_          | Bearer token passed through to the api-client. Set via ref, not markup. |
| `z-index`  | no       | `2147483000`     | Stacking context passthrough for `--rosie-z-index`.                     |

\* `api-base` is required for live use; the widget is fully functional in its
offline state without it (see §6).

Per-app accents (auto-derived):

| app       | accent      |
| --------- | ----------- |
| a11oy     | `#00d4ff` cyan |
| amaru     | `#f5b32a` gold |
| sentra    | `#3ddc84` green |
| vessels   | `#0099cc` ocean-cyan |
| rosie     | `#ff7a59` coral |

---

## 3. CSS variables the host may set

The widget reads two custom properties from the host. Set them on `:root` or
on the `<rosie-widget>` element itself; they are inherited into the Shadow DOM.

| Variable          | Default       | Purpose                                                          |
| ----------------- | ------------- | ---------------------------------------------------------------- |
| `--rosie-z-index` | `2147483000`  | Stacking order of the launcher, panel, and modal layers.         |
| `--rosie-accent`  | derived from `app` | Single accent color for button, panel highlights, and confirm dialog. |

```css
/* host stylesheet override example */
rosie-widget {
  --rosie-z-index: 9000;
  --rosie-accent: #00d4ff;
}
```

All other tokens (`--rosie-bg`, `--rosie-text`, radii, shadows) are internal
and may change between versions.

---

## 4. Shadow DOM (confirmed)

The element and every child component extend `LitElement`, which renders into
an **open Shadow DOM by default**. Consequences the host can rely on:

- Widget CSS does **not** leak into the host page.
- Host CSS does **not** leak into the widget (except the inherited custom
  properties listed in §3, which is intentional).
- The host's class names, resets, and global selectors cannot restyle the
  widget's internals.

---

## 5. Global-listener discipline

The widget registers exactly **one** global listener: a `keydown` handler on
`window` for `⌘K` (macOS) / `Ctrl-K` (others) that opens the command palette.

- It is added in `connectedCallback`.
- It is removed in `disconnectedCallback` (verified: the same bound reference
  is used for `addEventListener` and `removeEventListener`).
- No other `window`, `document`, or `body` listeners are added. All other event
  handling lives inside the component shadow roots.

The host therefore gets a clean teardown: unmounting `<rosie-widget>` leaves no
listeners behind.

---

## 6. Network and session discipline

- **No network call until configured.** With an empty `api-base` the api-client
  short-circuits every method with `ApiNotConfiguredError` and the panel shows
  a "configure api-base" message.
- **Reuse the host session.** All requests use `credentials: 'include'`, so the
  browser attaches the host's existing cookies/session. The widget never reads,
  copies, or stores `document.cookie`, and it persists no tokens.
- **Token passthrough (optional).** If the host sets `token`, it is sent as
  `Authorization: Bearer …` and never logged.
- **App-scoped.** Every request carries `?app=<app>`, so receipts and actions
  are filtered to the hosting application server-side.

### rosie-api endpoints the widget consumes

| Method | Path                                   | Purpose                                |
| ------ | -------------------------------------- | -------------------------------------- |
| POST   | `/v1/ask?app=<app>`                    | Ask a question; may return a proposed action. |
| GET    | `/v1/receipts?app=<app>&limit=<n>`     | Recent receipts for the app.           |
| GET    | `/v1/receipts/{id}/verify?app=<app>`   | Verify a receipt's signature/chain.    |
| POST   | `/v1/actions/confirm?app=<app>`        | Confirm + sign a proposed action.      |
| GET    | `/v1/receipts/stream?app=<app>` (SSE)  | Live receipt stream.                   |

Receipt payloads conform to `OperationalReceipt` from
`@szl-holdings/a11oy-receipt-substrate` (schema_version `1.0.0`).

---

## 7. Iframe embedding

The widget works inside an iframe (the standalone admin-console case):

- Every fixed-positioned layer (`launcher`, `panel`, `modal`) anchors to the
  **iframe viewport**, not the parent document, because they use plain
  `position: fixed` with no `transform` ancestor.
- The `⌘K` / `Ctrl-K` listener attaches to the iframe's own `window`, so it
  only fires when the iframe has focus and never interferes with the parent.
- `credentials: 'include'` follows the iframe's origin/cookie policy; if the
  iframe is cross-origin, the host must configure CORS + `SameSite` on the
  rosie-api accordingly.

---

## 8. Accessibility contract

- Launcher is a real `<button>` with an `aria-label`.
- Panel is `role="dialog" aria-modal="true"` with a focus trap; `Esc` closes it
  and focus returns to the launcher.
- Confirm dialog is a nested `role="dialog" aria-modal="true"` with its own
  focus trap; `Esc` cancels.
- Receipt cards are `<article>` elements with descriptive `aria-label`s; the
  stream region is an `aria-live="polite"` log.
- `prefers-reduced-motion` disables the ambient pulse and slide animations.

---

## 9. Versioning

- Package: `@szl-holdings/rosie-widget`, semver.
- CDN path is pinned per release: `…/rosie-widget/v<MAJOR.MINOR.PATCH>/…`.
- The `OperationalReceipt` schema version is carried on every receipt
  (`schema_version`), so a host can detect a contract mismatch at runtime.
