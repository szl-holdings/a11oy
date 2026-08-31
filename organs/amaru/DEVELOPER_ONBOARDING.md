# amaru — Developer Onboarding

> **Doctrine v11 LOCKED** · 749 declarations · 14 axioms · 163 sorries · Λ = Conjecture 1 · SLSA L1 honest

---

## 1. What amaru actually is

amaru is the **memory cortex** organ. It provides:

1. **7-Chakra reasoning pipeline** — ASCEND/DESCEND serpentine pipeline; each chakra emits a receipt trace entry.
2. **FAISS RAG with chunk-level citation** — every memory read/write wrapped in a Khipu receipt chain.
3. **Wire E subscriber** — receives brand-decision events from a11oy via SSE at `/api/amaru/v1/cortex-subscribe`.
4. **Wire F ingest endpoint** — receives gate-decision receipts from a11oy at `POST /api/amaru/v1/receipts/ingest`.
5. **Cardano L1 anchoring** — demo-seeded, NOT mainnet (see KNOWN_GOTCHAS.md).

---

## 2. Architecture diagram

```
  HF Space: SZLHOLDINGS/amaru  (port 7860)
  ┌──────────────────────────────────────────────────────┐
  │  serve.py (FastAPI outer shell)                      │
  │  ├── /                 Memory-cortex landing (SPA)   │
  │  ├── /conduit/*        Reverse-ETL React SPA          │
  │  ├── /console/*        Operator console SPA           │
  │  └── /api/amaru/* ──► amaru.app (inner FastAPI)       │
  │        ├── /v1/brainz        7-chakra reasoning       │
  │        ├── /v1/cortex-subscribe  SSE Wire E bus        │
  │        ├── /v1/receipts/ingest   Wire F DAG ingest     │
  │        ├── /v1/lambda            Lambda Λ score        │
  │        ├── /v1/honest            Doctrine posture      │
  │        └── /healthz              Liveness              │
  └──────────────────────────────────────────────────────┘
       Wire E (SSE) ◄─── a11oy sends brand-decision events
       Wire F (POST) ◄── a11oy sends gate-decision receipts
```

---

## 3. Sidecar import guard (CRITICAL — read before touching amaru.app)

`serve.py` imports the inner cortex app inside a try/except:

```python
try:
    from amaru.app import app as amaru_app
except Exception as _amaru_imp_err:
    # Falls back to JSON-503 stub — NEVER serves HTML from /api/amaru/*
```

**Why this matters**: if the inner app fails, the stub ensures `/api/amaru/*`
always returns JSON (not HTML). The frontend hook parses the response as JSON;
an HTML error page produces a cryptic client-side error. Do not remove this guard.

---

## 4. Running locally

```bash
# FULL clone (never --depth 1)
git clone https://github.com/szl-holdings/amaru.git && cd amaru
pip install fastapi uvicorn httpx cryptography pydantic numpy faiss-cpu
PORT=7860 uvicorn serve:app --host 0.0.0.0 --port 7860 --reload
```

---

## 5. Endpoint map

```
GET  /                              Memory-cortex landing
GET  /conduit/*                     Reverse-ETL SPA
GET  /api/amaru/healthz             Liveness
POST /api/amaru/v1/brainz           7-chakra reasoning
GET  /api/amaru/v1/cortex-subscribe SSE Wire E event stream
POST /api/amaru/v1/receipts/ingest  Wire F Khipu DAG ingest
GET  /api/amaru/v1/lambda           Lambda Λ score surface
GET  /api/amaru/v1/honest           Doctrine posture (749/14/163)
POST /api/amaru/v1/cortex/with-rosie Dual cortex+Rosie answer
```

---

## 6. HF Space deploy caveats

Same as a11oy: `hf-sync.yml` syncs README.md only.
Space: `SZLHOLDINGS/amaru` (https://szlholdings-amaru.hf.space).

---

## 7. Doctrine constants (LOCKED)

749/14/163 · kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 honest.

---

## 8. Key module index

| Module | Purpose |
|---|---|
| `serve.py` | Outer FastAPI shell + sidecar import guard |
| `szl_rag.py` | FAISS RAG retrieval core |
| `szl_rag_hnsw.py` | HNSW index variant |
| `szl_provenance.py` | DSSE + Khipu receipt chain |
| `szl_philosopher_loops.py` | 7-chakra pipeline |
| `szl_dsse.py` | DSSE signing (shared with a11oy) |
| `szl_wire.py` | Wire D/E/F wiring (shared) |
| `szl_be_hardening.py` | Backend hardening (shared) |
| `szl_bls_aggregate.py` | BLS12-381 aggregate signatures |

---

*Authored by Perplexity Computer Agent on behalf of Yachay (CTO).*
*Doctrine v11 LOCKED · 749/14/163 · Λ = Conjecture 1.*
*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
