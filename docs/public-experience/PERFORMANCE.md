<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Public experience v1 performance contract

## Budgets

| Concern | Contract | Verification |
|---|---|---|
| Initial product copy | At most 35 visible hero words | Static release gate and browser DOM readback |
| 3D startup | Lazy after the semantic experience is interactive | Browser network and renderer-state inspection |
| Device pixel ratio | Capped by the renderer | Source contract and browser inspection |
| Concurrent render loops | One active loop; pause off-screen or hidden | Behavioral tests and browser observation |
| Reduced motion | Designed 2D graph remains fully operable | Emulated reduced-motion browser run |
| Session memory | Bounded sessions, receipts, idempotency keys, rate-limit buckets, and TTL | Backend behavioral tests and health response |
| Request bodies | 16 KiB create/approval; 128 KiB receipt verification | Backend boundary tests |
| SSE | Ordered finite replay, no orphan background worker | Backend event-stream tests |

## Loading strategy

The semantic HTML, CSS, and small controller are sufficient to understand and
operate the product. The renderer is a progressive enhancement loaded only when
the browser and user preferences permit it. Three.js remains vendored under
`/static/3d/vendor/`; no runtime CDN or tracking script is added.

The renderer uses state-derived node counts, caps pixel density, and disposes
its animation frame, listeners, observers, geometry, and materials. The
controller aborts superseded fetches and event-stream reads. These constraints
avoid multiplying CPU, GPU, network, or memory work when a visitor launches a
new scenario or returns to the page.

## Evidence status

Source/build checks are necessary but do not establish real browser timing or
Core Web Vitals. Record desktop/mobile browser observations and any measured
timings in `RELEASE_EVIDENCE.md` after the rebased build is exercised. Record
production measurements only after the deployed revision is source-bound.
