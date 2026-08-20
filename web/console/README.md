# a11oy operator console (SPA)

A small, self-contained operator console for a11oy with **6 working routes**,
each backed by a real `a11oy serve` HTTP endpoint.

| Route | Label | a11oy endpoint |
| --- | --- | --- |
| `/` | Health | `GET /healthz` + `GET /readyz` |
| `/ledger` | Proof Ledger | `GET /v1/ledger?limit=N` |
| `/receipt/:hash` | Receipt | `GET /v1/ledger/{hash}` |
| `/verify` | Verify | `POST /v1/verify` |
| `/policy` | Policy | `POST /v1/policy/evaluate` |
| `/khipu-demo` | Khipu Demo | `GET /api/khipu/demo` |

The `/khipu-demo` tab shows **three RECORDED** Khipu navigator traces
(navigation success, governance abstain, and one honest abstain **failure**) with
copy-to-clipboard buttons for the input JSON, output JSON, and the one-line local
run command. It is explicitly **not live inference** and **not the signed-receipt
artifact** — the traces were AGENT-RUN on the quantized (Q4_K_M) GGUF on CPU via
llama.cpp, and ship in-image (no external fetch at runtime).

## Why this exists

The mining audit recorded that a11oy's existing web surface (`web/src/App.tsx`,
~470 lazy imports) depends on ~30 platform workspace packages that are not part
of this repository, so it cannot build here. The audit's instruction was to
give the SPA the **5 working routes from the mined route surface** rather than
resurrect the dead-import surface.

This console is that deliverable. The 5 routes are derived from the mined a11oy
MCP/CLI route surface and wired to the HTTP endpoints a11oy actually serves
(see `packages/receipt-substrate/src/serve.ts`, the `a11oy serve` subcommand).

The legacy surface in `web/src/` is **left in place** (Operating Principle #10:
annotate stale content, do not silently delete). This console is additive and
self-contained: its only dependencies are `react`, `react-dom`, and `wouter`.

## Run

```
# 1. start a11oy's HTTP server (the data source)
a11oy serve --port 8080

# 2. start the console (dev proxies /v1, /healthz, /readyz to :8080)
cd web/console && npm install && npm run dev
```

Point at a remote substrate with `VITE_A11OY_BASE_URL=https://a11oy.example`.

## Test

```
npm test   # node --experimental-strip-types src/a11oyClient.test.ts
```

The test boots a real `node:http` server matching the `a11oy serve` route
contract and exercises every route's backing call over real TCP via Node's
global `fetch` — no transport mock.

## License

Apache-2.0 © 2026 SZL Holdings (Stephen P. Lutar Jr., ORCID 0009-0001-0110-4173)
