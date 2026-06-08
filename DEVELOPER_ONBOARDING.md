# a11oy — Developer Onboarding

> **Doctrine v11 LOCKED** · 749 declarations · 14 axioms · 163 sorries · Λ = Conjecture 1 · SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap

This document is the single entry point for a new developer joining a11oy.
Read it top-to-bottom once; after that, `serve.py` + `szl_dsse.py` are the
best daily navigation anchors.

---

## 1. What a11oy actually is

a11oy is the **Brand Orchestration Layer** and the SZL platform's root of trust.
In practice it does three things:

1. **Serves the investor-facing React SPA** (Vessels-DNA, Vite-built) at `/`.
2. **Exposes the policy-gate API** — 46 governed policy gates, each producing a signed Khipu receipt.
3. **Acts as the mesh hub** for other organs (sentra, amaru, killinchu, rosie) via Wire A/B/C/D/E/F wiring (`szl_wire.py`).

Everything runs as a single FastAPI process on HF Spaces at port 7860.
A sidecar Node process (port 8081) serves the TypeScript receipt-substrate API;
Python proxies `/api/a11oy/*` to it.

---

## 2. Architecture diagram

```
  HF Space: SZLHOLDINGS/a11oy  (port 7860)
  ┌──────────────────────────────────────────────────┐
  │  serve.py (FastAPI)                              │
  │  ├── /               SPA index.html (Vite dist) │
  │  ├── /assets/*       JS/CSS chunks               │
  │  ├── /api/a11oy/v1/gates   46 policy gates (Py) │
  │  ├── /api/a11oy/yachay/*   Yachay CTO organ      │
  │  └── /api/a11oy/*   ──proxy──► Node :8081        │
  │                              (receipt-substrate)  │
  │                                                  │
  │  Key modules (flat at repo root):                │
  │  szl_dsse.py        DSSE receipt signing         │
  │  szl_khipu.py       Khipu DAG (in-memory)        │
  │  szl_wire.py        Cross-pod mesh wiring        │
  │  szl_be_hardening.py  Rate-limit, SQLite, OTel   │
  │  szl_lambda_tripwire.py  Lambda halt guard        │
  │  szl_yachay_organ.py    CTO chat organ            │
  │  szl_formulas.py    Formula/gate evaluation       │
  └──────────────────────────────────────────────────┘
       │ Wire B (verdict)    │ Wire E (cortex events)
       ▼                     ▼
   sentra (immune)       amaru (reasoning)
```

---

## 3. Running locally

### Prerequisites

- Python 3.12+, Node 22+, pnpm
- Docker (optional — easiest path)

### Fastest: Docker

```bash
docker run --rm -p 7860:7860 ghcr.io/szl-holdings/a11oy:uds-v0.2.0
curl http://localhost:7860/api/a11oy/healthz
```

### Manual (for active dev)

```bash
# 1. FULL clone (never --depth 1 — see KNOWN_GOTCHAS.md)
git clone https://github.com/szl-holdings/a11oy.git && cd a11oy

# 2. Python
pip install fastapi uvicorn httpx cryptography py_ecc

# 3. Node sidecar
pnpm install && pnpm -F @szl-holdings/receipt-substrate build
node dist/packages/receipt-substrate/src/serve.js &

# 4. Optional: real DSSE signing (leave unset for PLACEHOLDER mode)
# export SZL_COSIGN_PRIVATE_KEY_PEM="$(cat cosign.key)"  # NEVER commit this

# 5. Start
PORT=7860 uvicorn serve:app --host 0.0.0.0 --port 7860 --reload
```

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `PORT` | No (default 7860) | HF enforces 7860 in production |
| `SZL_COSIGN_PRIVATE_KEY_PEM` | No | ECDSA P-256 PEM → real DSSE signing; absent = PLACEHOLDER |
| `SZL_COSIGN_PRIVATE_PEM` | No | Backward-compat alias for above |
| `HF_TOKEN` | For HF push only | Used by hf-sync workflow |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | Enable OTLP trace export |

---

## 4. Where the key logic lives

| Concern | File | Entry point |
|---|---|---|
| FastAPI app + route registration | `serve.py` | `app` object |
| 46 policy gates | `szl_formulas.py` | `evaluate_gate()` |
| DSSE signing/verification | `szl_dsse.py` | `sign_payload()`, `verify_payload()` |
| Khipu DAG receipt chain | `szl_khipu.py` | `KhipuDAG.emit()` |
| Cross-pod mesh wiring | `szl_wire.py` | `install_traceparent_middleware()` |
| Rate-limit + structured logs | `szl_be_hardening.py` | `harden(app, organ=...)` |
| Lambda halt guard | `szl_lambda_tripwire.py` | `LambdaTripwireTriggered` |
| Yachay CTO organ | `szl_yachay_organ.py` | `attach(app)` |

---

## 5. Endpoint map

```
GET  /                          SPA (Vessels-DNA landing)
GET  /assets/*                  Vite JS/CSS chunks
GET  /api/a11oy/healthz         Liveness
GET  /api/a11oy/readyz          Readiness (Khipu chain check)
GET  /api/a11oy/v1/gates        List all 46 policy gates
GET  /api/a11oy/v1/gates/{name} Single gate + sample
POST /api/a11oy/v1/reason       Reasoning (gate-aware)
POST /api/a11oy/v1/policy/evaluate  -> Node :8081
GET  /api/a11oy/v1/honest       Live doctrine posture (749/14/163)
GET  /api/a11oy/v1/ledger       -> Node :8081
GET  /yachay                    Yachay CTO chat UI
POST /api/a11oy/yachay/chat     Yachay chat (Khipu-receipt-signed)
GET  /{anything}                SPA history fallback -> index.html
```

---

## 6. How the HF Space deploy works (IMPORTANT — read before pushing)

GitHub and the HF Space are NOT a simple git mirror. The `hf-sync` workflow
syncs **only README.md** (front-matter prepended) via `huggingface_hub.create_commit`.
Application Python code does NOT sync automatically.

Code reaches the Space via:
1. GHCR image build (`ghcr-build-push.yml`) + Dockerfile tag bump on the Space.
2. Direct commit to the HF Space git repo (separate from GitHub).

**Footgun**: pushing Python changes to GitHub main does NOT update the running
Space unless the GHCR image is rebuilt. See `KNOWN_GOTCHAS.md`.

---

## 7. Running the tests

```bash
# Python
pip install pytest && pytest tests/ -v

# TypeScript
pnpm install
pnpm -F @szl-holdings/receipt-substrate test
pnpm -F @a11oy/core test:doctrine   # REQUIRED before any core PR

# Smoke (live Space)
bash scripts/smoke-from-public-url.sh
```

---

## 8. Doctrine constants (LOCKED)

| Constant | Value |
|---|---|
| Declarations | 749 |
| Axioms | 14 unique (15 raw, 1 dup) |
| Sorries | 163 (112 baseline + 51 Putnam) |
| Kernel commit | `c7c0ba17` |
| Lambda uniqueness | Conjecture 1 — NOT a theorem |
| SLSA | L1 honest (cosign-signed image, Rekor-verifiable); L2 roadmap via Wire D — not yet claimed; L3 not claimed |

---

## 9. The try/except organ registration pattern

Every optional module is imported inside `try/except` in `serve.py`:

```python
try:
    import szl_be_hardening as _be_harden
    _be_harden.harden(app, organ="a11oy")
except Exception as _be_e:
    print(f"[a11oy] BE hardening NOT registered: {_be_e!r}", file=sys.stderr)
```

This is intentional: HF Spaces have no restart supervisor. A crash at import time
takes the entire Space down with no easy recovery. If you add a new module, follow
this pattern. A module silently missing = missing Dockerfile COPY line (see
KNOWN_GOTCHAS.md).

---

## 10. First PR checklist

- [ ] `pnpm -F @a11oy/core test:doctrine` — all six invariants must pass
- [ ] `pytest tests/ -v` — no regressions
- [ ] DCO sign-off: `git commit -s`
- [ ] Do NOT change doctrine numbers (749/14/163) without a doctrine version bump
- [ ] Do NOT call Lambda uniqueness "proven" or "theorem"
- [ ] New Python module? Add a matching `COPY` line in Dockerfile

---

*Authored by Perplexity Computer Agent on behalf of Yachay (CTO).*
*Doctrine v11 LOCKED · 749/14/163 · Λ = Conjecture 1.*
*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
