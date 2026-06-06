# KNOWN_GOTCHAS.md — amaru

> Doctrine v11 LOCKED · 749/14/163.

---

## 1. GitHub ↔ HF Space drift

Same as a11oy: `hf-sync.yml` only syncs `README.md`.
Space: `SZLHOLDINGS/amaru` (https://szlholdings-amaru.hf.space).

---

## 2. Sidecar import — JSON 503 fallback (NOT an error)

If `from amaru.app import app` fails at startup, the try/except stub returns
JSON 503 from all `/api/amaru/*` routes. Check Space logs for:
`[amaru] CRITICAL: amaru.app import failed`.

Do NOT let `/api/amaru/*` routes return HTML. The frontend parses these as
JSON; an HTML error page produces a hard-to-debug client-side parse error.

---

## 3. FAISS in slim Docker images

`faiss-cpu` is a heavy binary. On slim Alpine bases it may not install.
The RAG routes are wrapped in try/except and degrade honestly if absent.

---

## 4. Cardano anchor is demo-seeded (NOT mainnet)

The Cardano L1 feature uses pre-seeded demo data. NOT connected to mainnet.
`/v1/honest` says `cardano_anchor: "demo_seeded"`. Never document as on-chain.

---

## 5. Wire E is an in-memory ring buffer

The SSE event bus uses `deque(maxlen=200)`. Events are real but not durable
(restart = loss). No Kafka/NATS wired. Honestly disclosed in `/v1/brainz`.

---

## 6. Dockerfile per-file COPY discipline

Same as a11oy: every module needs a `COPY` line. Missing = silent 404.

---

## 7. `from __future__ import annotations` FastAPI gotcha

Avoid in files defining FastAPI routes or Pydantic models.

---

## 8. Shallow clone

`git ls-files | wc -l` should be ~397. If < 50, partial checkout.

---

*Signed-off-by: stephenlutar2-hash <stephenlutar2@gmail.com>*
