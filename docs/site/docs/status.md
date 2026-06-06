# Status

Live operational status of the SZL surfaces. This page is a static snapshot of the canonical
endpoints; for real-time liveness, hit each service's `/healthz` directly.

## Live flagship services

| Surface | Endpoint | Liveness check |
|---------|----------|----------------|
| **a11oy** | [szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space) | `GET /healthz` → doctrine v11 · 749/14/163 |
| **amaru** | [szlholdings-amaru.hf.space](https://szlholdings-amaru.hf.space) | `GET /healthz` |
| **killinchu** | [szlholdings-killinchu.hf.space](https://szlholdings-killinchu.hf.space) | `GET /api/killinchu/healthz` |
| **rosie** | [szlholdings-rosie.hf.space](https://szlholdings-rosie.hf.space) | `GET /healthz` |
| **sentra** | [szlholdings-sentra.hf.space](https://szlholdings-sentra.hf.space) | `GET /api/sentra/healthz` |
| Anatomy-3D | [szlholdings-anatomy-3d.static.hf.space](https://szlholdings-anatomy-3d.static.hf.space/) | static Space |
| Rosie-3D | [szlholdings-rosie-3d.static.hf.space](https://szlholdings-rosie-3d.static.hf.space/) | static Space |
| MCP receipts server | [szlholdings-mcp-receipts-server.hf.space](https://szlholdings-mcp-receipts-server.hf.space) | `GET /gradio_api/info` (17 tools) |

All five flagship `/healthz` endpoints return Doctrine v11 verbatim:
`749 declarations / 14 unique axioms / 163 tracked sorries`, locked at `c7c0ba17`.

## Repositories

All flagship repos run CI, CodeQL, SBOM, and DCO workflows on `main`:

- [a11oy](https://github.com/szl-holdings/a11oy) · [amaru](https://github.com/szl-holdings/amaru) ·
  [sentra](https://github.com/szl-holdings/sentra) · [killinchu](https://github.com/szl-holdings/killinchu) ·
  [rosie](https://github.com/szl-holdings/rosie)
- [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel) ·
  [ouroboros-thesis](https://github.com/szl-holdings/ouroboros-thesis) ·
  [szl-cookbook](https://github.com/szl-holdings/szl-cookbook) ·
  [szl-brand](https://github.com/szl-holdings/szl-brand)

::: info Dedicated status page
A dedicated, auto-refreshing status page (uptime history + incident log) is **in development**.
Until it ships, this page is the canonical endpoint list and each service's `/healthz` is the
real-time source of truth.
:::

## Known honest-status items

- **cosign signing:** PENDING — DSSE signatures are `PLACEHOLDER` (see [Compliance](/compliance)).
- **Cardano mainnet anchoring (amaru):** in development.
- **Wire D (W3C traceparent):** in-process tracing is **LIVE** on every request; cross-Space
  distributed-trace broker is **NOT wired** (roadmap). See [WIRES D–H](/architecture).
- **Wire E–H (cortex SSE, Khipu receipts, brain mesh, lean-verify):** **LIVE in-process**
  within each Space; cross-Space orchestration layer is roadmap.
- **UDS public demo:** launches Warhacker Jun 16, 2026 — not yet live.
- **Unified SDKs (szl-python, szl-ts):** in development.

*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · SLSA L1 honest*
