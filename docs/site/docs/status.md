# Status

Live operational status of the SZL surfaces. This page is a static snapshot of the canonical
endpoints; for real-time liveness, hit each service's `/healthz` directly.

## Live flagship services

Two flagships ship today and expose live `/healthz`:

| Surface | Endpoint | Liveness check |
|---------|----------|----------------|
| **a11oy** (governed execution fabric) | [szlholdings-a11oy.hf.space](https://szlholdings-a11oy.hf.space) | `GET /healthz` → doctrine v11 · 749/14/163 |
| **killinchu** (drone-intelligence / counter-UAS) | [szlholdings-killinchu.hf.space](https://szlholdings-killinchu.hf.space) | `GET /api/killinchu/healthz` |
| Anatomy-3D (static showcase) | [szlholdings-anatomy-3d.static.hf.space](https://szlholdings-anatomy-3d.static.hf.space/) | static Space |
| **Hatun-MCP** (Model Context Protocol) | [szlholdings-hatun-mcp.hf.space](https://szlholdings-hatun-mcp.hf.space/mcp/) | `POST /mcp/` JSON-RPC `initialize` → 23 static tools. **Re-deploying** (see note). |

Both shipping flagship `/healthz` endpoints return Doctrine v11 verbatim:
`749 declarations / 14 unique axioms / 163 tracked sorries`, locked at `c7c0ba17`.

## Repositories

Flagship repos run CI, CodeQL, SBOM, and DCO workflows on `main`:

- [a11oy](https://github.com/szl-holdings/a11oy) ·
  [killinchu](https://github.com/szl-holdings/killinchu)
- [lutar-lean](https://github.com/szl-holdings/lutar-lean) (kernel) ·
  ouroboros-thesis ·
  [szl-cookbook](https://github.com/szl-holdings/szl-cookbook) ·
  [szl-brand](https://github.com/szl-holdings/szl-brand)

::: info Dedicated status page
A dedicated, auto-refreshing status page (uptime history + incident log) is **in development**.
Until it ships, this page is the canonical endpoint list and each service's `/healthz` is the
real-time source of truth.
:::

## Known honest-status items

- **Hatun-MCP (`szlholdings-hatun-mcp.hf.space/mcp/`):** the fleet's only spec-compliant
  Streamable HTTP MCP server (23 static tools). The hosted Space is being re-deployed from
  [szl-holdings/hatun-mcp](https://github.com/szl-holdings/hatun-mcp) (a Dockerfile fix restores
  the build); until it returns `200`, run the server locally per its README. The shipping flagship
  Spaces (a11oy/killinchu) expose tools as **HTTP catalogs** at `/api/<organ>/v1/mcp/tools`,
  not as an MCP transport.
- **Roadmap surfaces not yet deployed (removed from the live table):** the Provenance Anchor,
  Operator, and Policy components (internal codenames *amaru*, *rosie*, *sentra* — retired) have
  **no live Space today** (`szlholdings-amaru/rosie/sentra.hf.space` return HTTP 404) and are
  roadmap/frontier roles, not shipping services. The former `Rosie-3D` showcase is likewise not
  deployed. They are documented honestly under [Flagships](/flagships/).
- **"MCP receipts server" Space:** **removed from this table** — `szlholdings-mcp-receipts-server.hf.space`
  is not deployed (HTTP 404) and has no backing repo. Receipt signing/verification is live today via
  each shipping flagship's `/khipu/sign` · `/khipu/verify` · `/khipu/pubkey` routes (a11oy verified).
- **cosign signing:** PENDING — DSSE signatures are `PLACEHOLDER` (see [Compliance](/compliance)).
- **Cardano mainnet anchoring (Provenance Anchor):** in development.
- **Wire D (W3C traceparent):** in-process tracing is **LIVE** on every request. A bounded,
  closed-registry cross-mesh hop can now be run explicitly with
  `POST /api/a11oy/v1/wire-d/probe`; it is **MEASURED** only after the configured peer echoes
  the same trace ID and a Khipu receipt is appended. Read current evidence without mutation at
  `GET /api/a11oy/v1/wire-d/status`. This is not a general distributed-trace broker.
- **Wire E–H (cortex SSE, Khipu receipts, brain mesh, lean-verify):** **LIVE in-process**
  within each Space; cross-Space orchestration layer is roadmap.
- **UDS public demo:** launches Warhacker Jun 16, 2026 — not yet live.
- **Unified SDKs (szl-python, szl-ts):** in development.

*Doctrine v11 LOCKED · 749/14/163 · kernel c7c0ba17 · SLSA L1 honest*
