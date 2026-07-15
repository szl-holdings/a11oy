<!-- VENDORED FROM szl-holdings/platform@d487e5f1e702c13c59509448a80b5da2e5751ea2 — replit-sync/energy_engine/HOLOGRAM_NOTES.md -->
<!-- DO NOT EDIT HERE. Edit in the monorepo, then run scripts/sync_from_monorepo.sh sync. -->
# Holographic Command Bridge — build notes (`web/hologram.html`)

A single 3D immersive surface that renders the SZL **agentic-GPU as a living
organism**. Route: **`/hologram`** (and `/a11oy/hologram`), registered additively
in `serve.py` next to the other sovereign surfaces (`/fleet-c2`, `/energy`, …).

## What it renders
- **MIND core** — the RTX 5000 @ betterwithage as a central icosahedron "mind".
  Its wireframe shell + glow halo are **driven by `/code/healthz`**:
  - `sovereign:true` + `inference=self-hosted-gpu` → **green shell + sovereign glow ON**;
  - `sovereign:true` (other inference) → green, dimmer glow;
  - reachable but **not** sovereign → **amber, glow OFF** (the half-state is refused —
    we never show a sovereign halo for a router fallback);
  - unreachable → **grey "unknown", glow OFF** (honest empty-state).
- **6 organ nodes** orbiting the core — BRAIN / HEART / BLOOD / IMMUNE / SKELETON /
  NERVOUS, each a proven round9 formula (see `ANATOMY_SHELL_AGENTIC_BODY.md`).
  Each **probes its real endpoint** and:
  - reachable → **active**: bright, **pulsing** scale + emissive;
  - reachable-but-degraded → amber, slight jitter (reserved for explicit degraded signals);
  - unreachable → **dim, still "unknown"** — no fabricated activity.
  Hovering an organ shows a tooltip with its role + endpoint + live status.
- **Energy-flow particles** — streams flowing **from the outer field inward to the
  core**, colored by **energy source** (solar=gold, wind=cyan, hydro=blue,
  flare=orange, grid=grey). Stream count + color are **derived from
  `/v1/energy/budget`** receipts (dominant source by `joules_est`). **Zero receipts
  → zero streams** — we draw circulation only for confirmed activity.
- **Swarm constellation** — a faint outer ring of consent-only swarm nodes; count
  taken from `/v1/gates` when present, else a default 7-node fabric. The anchor
  node is tinted sovereign-green.

## Real endpoints read (honest, graceful degrade)
| Element | Endpoint | Degrade behavior |
|---|---|---|
| MIND posture / sovereign glow | `/api/a11oy/code/healthz` | grey "unknown", **no glow** |
| Energy circulation (flow color/volume) | `/api/a11oy/v1/energy/budget` | no streams, "—" labels |
| BRAIN | `/api/a11oy/v1/formulas` | dim "unknown" |
| HEART | `/api/a11oy/v1/receipts/summary` | dim "unknown" |
| BLOOD | `/api/a11oy/v1/khipu/health` | dim "unknown" |
| IMMUNE | `/api/a11oy/v1/gates` | dim "unknown" |
| SKELETON | `/api/a11oy/math/lean/theorems` | dim "unknown" |
| NERVOUS | `/api/a11oy/overwatch/snapshot` | dim "unknown" |

`getJSON()` never throws: any non-OK / network error returns `null`, and `null`
always maps to the honest dim/unknown state. Polls every 15 s. If WebGL is
unavailable, a fallback panel points to the JSON endpoints and the 2D `/energy`
surface, and the HUD cards are still driven from live JSON.

## Honesty / doctrine (v11/v12)
- **Sovereign glow ONLY when `/code/healthz` reports `sovereign:true`** — never assumed.
- **Energy figures are SAMPLE/ESTIMATE** — labeled `SAMPLE` on the card; no power
  meter is wired (per `DATA_SOURCES_WIRING.md`, NVML is the first MEASURED path, not yet live here).
- **Λ trust = Conjecture 1** — shown verbatim in the MIND card; never a theorem.
- **No fabricated data** — unreachable organs/sources render dim/empty, not green.
- **Consent-only swarm**; **no key**; **open-weight**.

## No-CDN posture
Three.js **r128 (MIT)** is the **already-vendored** `static-vendor/three.min.js`,
served at **`/vendor/three.min.js`** (the same global-`THREE` asset `fleet-c2.html`
uses). The page references no external URL — the glow sprite is generated
procedurally on a `<canvas>`, so we ship **no image asset** and **0 runtime CDN**.

## Verification
- `python3 -c "import ast; ast.parse(open('serve.py').read())"` → OK (route added additively).
- Inline `<script>` extracted → **`node --check` → OK** (no headless browser available;
  **a deploy preview is needed** to confirm the live WebGL render + endpoint binding).
- CDN audit: no external `http(s)` URLs in `hologram.html`.
- Tag-balance check: `script/style/div/body/html/canvas` all balanced.

## Dependencies
- The `/energy`, `/code/healthz`, `/v1/energy/budget` surfaces/endpoints land via
  a11oy PR **#332** (`feat/energy-dashboard`) — this PR is **stacked on that branch**.
- Three.js vendoring + `/vendor/{fname}` allowlist already in `serve.py` (includes `three.min.js`).
