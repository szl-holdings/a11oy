# Khipu 3D — Live Receipt DAG (Greene Demo · Beat 3)

A single, browser-based 3D visualization of the **live, signed, traceable Khipu
receipt DAG** across all five SZL organs. Built on `three.js` + `3d-force-graph`,
vanilla HTML + CSS + JS — **no build step, fast first paint**.

> When Greene sees this, the science lands. The math becomes visible.

## What it shows (REAL DATA, no mocks)

| Channel | Mapping | Source |
| --- | --- | --- |
| **Node** | one real DSSE-signed Khipu receipt | `/api/<organ>/khipu/ledger` |
| **Node color** | Λ verdict — green ≥0.8, amber 0.5–0.8, red <0.5 | derived from real receipt facts (signed? + valid traceparent + co-signer count) |
| **Node size** | Welford online variance of the Λ stream | `data-adapter.js` (Welford 1962) |
| **Edge (Wire F)** | DSSE Merkle parent chain inside an organ ledger | `node.parents[0]` digest links |
| **Edge (Wire D)** | W3C `traceparent` continuation across organs (same `trace_id`) | receipt `traceparent` / `trace_id` |
| **Edge color** | which Wire (B, C, D, E, F, G) | `theme.css` palette |
| **Label** | `organ · …trace8 · λ · timestamp` | live receipt |
| **Pulse** | particles fired along edges when a NEW receipt arrives (3s poll) | diff vs. last snapshot |

Hover any node to see **the formula that produced its Λ**, cited by name +
real source (see `formulas.js` for the honest page map of `thesis_v22.pdf`).

## Honesty posture (HARD RULE)

- Every node is backed by a **real receipt** pulled live from an organ ledger.
- `a11oy` is honestly shown as `BUILD_ERROR` when its Space is down — **never**
  faked into the graph.
- Λ is derived **deterministically from real receipt facts only** (no randoms).
  If a receipt carries an explicit numeric `lambda`/`verdict_value`, that real
  value is used verbatim instead.
- Formula citations only attribute a `thesis_v22.pdf` **page** to formulas that
  are actually printed there (BLS, Byzantine quorum, Holevo → **p2 §1.5**).
  PAC-Bayes and Welford are cited to their **real repo implementation**
  (`szl_formulas.py`, `szl_khipu_consensus.py`) with an explicit
  "not named in v22 p1–3" note. No page numbers are invented.

## Failsafe chain

1. **Preferred:** `GET /api/rosie/v1/khipu/aggregate` — the rosie server fans
   out to every organ, marks down organs honestly, returns one snapshot.
2. **Fallback:** browser polls each `/api/<organ>/khipu/ledger` directly (CORS
   is open on the organ Spaces).
3. **Cache:** last successful snapshot is kept in `localStorage`
   (`khipu3d:lastSnapshot`) and rendered if both live paths fail.
4. **Honest empty:** if even the cache is empty → "Mesh quiescent — refresh to
   reload". Never fake nodes.

## Deploy

### A. As a static path on the rosie Space (preferred)
`rosie/serve.py` (and the live `app.py`) mount this directory at `/khipu-3d/*`
and expose `/api/rosie/v1/khipu/aggregate`. Once the Space builds:

```
https://szlholdings-rosie.hf.space/khipu-3d
```

### B. Standalone single-file (failsafe for the demo)
If the HF Space is still `BUILD_ERROR`, open **`khipu-3d.html`** (one file, inline
JS + CSS) directly in any browser or drop it on any web host. It points at the
public organ Spaces, so it works from anywhere with network access.

```
open web/khipu-3d/khipu-3d.html      # or host it anywhere
```

## Files

```
web/khipu-3d/
├── index.html        # multi-file entry (served at /khipu-3d)
├── khipu-3d.js       # three.js + 3d-force-graph renderer, pulse, hover beat
├── data-adapter.js   # live fetch from all 5 organs, Λ + Welford, edges, cache
├── formulas.js       # formula tooltips + honest thesis_v22 page map
├── theme.css         # Inca palette (hatun gold/ochre, yawar terra cotta, indigo)
├── khipu-3d.html     # STANDALONE single-file artifact (inline everything)
└── README.md         # this file
```

---

```
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
```
