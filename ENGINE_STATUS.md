# Unified Engine Status — the one feed the whole organism reports through

`szl_engine_status.py` adds a single read-only endpoint:

```
GET /api/a11oy/v1/engine/status
```

It aggregates the **whole agentic-GPU organism** — the MIND (the RTX 5000 @
betterwithage) plus its 8-organ anatomy BODY — into **one honest JSON**. This is
the single feed the 3D hologram (F1) and every dashboard consume, so the living
system is one endpoint instead of N scattered probes.

## Shape of the payload

```jsonc
{
  "schema": "szl.engine_status/v1",
  "ts_utc": "2026-06-13T…Z",
  "mind":   { "sovereign": false, "posture": "…", "inference": {…}, "gpu": {…}, "base_url": "…", "reachable": true },
  "organs": {
    "brain":    { "reachable": true,  "status": "ok",          "endpoint": "/api/amaru/v1/formulas" },
    "heart":    { "reachable": true,  "status": "ok",          "endpoint": "/api/amaru/receipts" },
    "blood":    { "reachable": false, "status": "unreachable", "endpoint": "/api/sentra/khipu/ledger" },
    "immune":   { "reachable": true,  "status": "ok",          "endpoint": "/api/sentra/v1/gates" },
    "skeleton": { "reachable": true,  "status": "ok",          "endpoint": "/api/amaru/v1/math/lean/theorems" },
    "nervous":  { "reachable": true,  "status": "ok",          "endpoint": "/api/amaru/overwatch/snapshot" }
  },
  "organs_healthy": 5, "organs_total": 6,
  "energy": { "window": "off-peak", "source": "nvml", "joules": { "value": 1234.5, "label": "measured" }, "within_bound": true, "reachable": true },
  "swarm":  { "nodes": 4, "served_by": "anchor", "reachable": true },
  "doctrine": { "lambda": "Conjecture 1", "locked": 8, "half_state": "forbidden", "version": "v11" }
}
```

## What each block reads from (live, read-only)

| Block | Source endpoint | Organ / formula |
|---|---|---|
| `mind` | `/code/healthz` | the GPU MIND — sovereign / posture / inference / gpu |
| `organs.brain` | `/api/amaru/v1/formulas` | BrainBeliefUpdate (PAC-Bayes McAllester) |
| `organs.heart` | `/api/amaru/receipts` | HeartReceiptSigma (σ-algebra receipt bus) |
| `organs.blood` | `/api/sentra/khipu/ledger` | BloodDSSEMerkle (Cardano-anchored DSSE) |
| `organs.immune` | `/api/sentra/v1/gates` | ImmuneNeymanPearson (8 deny-by-default gates) |
| `organs.skeleton` | `/api/amaru/v1/math/lean/theorems` | SkeletonLambdaSpine (the Lean kernel; Λ=Conj1) |
| `organs.nervous` | `/api/amaru/overwatch/snapshot` | NervousShannonAlarm (Λ-signed OTEL + drift) |
| `energy` | `/api/a11oy/v1/energy/budget` (#328) | Bekenstein budget — joules + window + bound |
| `swarm` | `/api/a11oy/v1/swarm/status` (#358) | consent-only node fabric — nodes + served_by |

Each sub-probe is an independent in-process GET with a timeout, run concurrently.
The aggregate **never fails** because one organ is down — that organ simply shows
`reachable:false`.

## Honesty by construction (Doctrine v11)

- **Never fabricate a status.** Every probe degrades honestly: a timeout, a
  connection refusal, or any non-2xx becomes `{"reachable": false, "status": …}`.
  An organ that is down is reported down — never bluffed green.
- **sovereign:true ONLY from `/code/healthz`.** `mind.sovereign` defaults to
  `false` and is set true **only** when the MIND's own health endpoint says so. If
  the MIND probe fails or is silent, sovereign is false. Sovereignty is never
  inferred from any other organ — that would be the forbidden half-state.
- **joules labeled honestly.** `energy.joules.label` is `"measured"` **only** when
  the budget feed reports a real metered figure (e.g. NVML `power.draw`); otherwise
  `"sample"`/`"estimate"`. No greenwashing.
- **Λ = Conjecture 1** is stated in the payload (the skeleton's killer formula is
  intentionally a conjecture — we say so). `locked: 8` (the round9 organ formulas,
  untouched). `half_state: "forbidden"`.
- **No key; open-weight; pure-stdlib aggregation.** The only runtime dependency is
  the app's existing in-process `httpx` client for the read-only probes.

## Wiring

`serve.py` imports the module in a `try/except` block and calls
`register(app, ns="a11oy")` EARLY — before the SPA `/{full_path:path}` catch-all —
exactly like the other `szl_*` modules. The handler resolves the shared
`_http_client` lazily at request time, so it is safe to register before the
startup event builds that client. A missing module can never take the Space down.

`base_url` defaults to `""` (same-origin loopback), which is correct because the
a11oy Space serves/proxies all the organ paths above. Point it at another origin
only if the organs move off-box.

## Self-test (no network, no GPU)

```bash
python3 szl_engine_status.py   # -> {"ok": true, "checks": 30, "failed": []}
```

Injects a fake fetcher (pure stdlib — no FastAPI/httpx needed) and verifies:
- **A** full healthy aggregate (6/6 organs, sovereign mind, MEASURED joules, swarm served_by);
- **B** one organ (immune) down → `reachable:false`, status labeled, the other 5 still reachable, aggregate did **not** fail;
- **C** MIND down → `sovereign` MUST be `false` (never fabricated);
- **D** MIND reachable but reports `sovereign:false` → stays false;
- **E** budget feed without a measured label → joules labeled `sample`;
- **F** swarm feed absent → `reachable:false`, `served_by:null` (never invented);
- **G** total outage → nothing reported green, doctrine block still present.

## Citations / dependencies

- Energy budget feed — platform/a11oy **#328** (`/v1/energy/budget`); provenance **#331**.
- Heart pulse / receipt bus — **#333** (`/v1/heart/pulse`, HeartReceiptSigma).
- Swarm registry — platform **#358** (`swarm.py`, consent-only, anchor-first sovereign).
- The 8 round9 organ formulas (BrainBeliefUpdate / HeartReceiptSigma / BloodDSSEMerkle /
  ImmuneNeymanPearson / SkeletonLambdaSpine / NervousShannonAlarm + yarqa FLOW) — see
  `energy_engine/anatomy/ANATOMY_SHELL_AGENTIC_BODY.md`.
