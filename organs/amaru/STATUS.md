# STATUS.md — amaru (Cortex Memory / Conduit)

**Updated:** 2026-06-02
**Doctrine v11 — 749 / 14 / 163 — replay hash c7c0ba17**

HF Space: <https://huggingface.co/spaces/SZLHOLDINGS/amaru>

---

## What's Live

- **HF Space** — amaru is deployed and operational on Hugging Face Spaces
- **`/healthz`** — returns Doctrine v11 numbers and service status
- **`/sign`** — Wire D DSSE signing endpoint
- **`/tick`** — DSSE-wrapped tick endpoint (heartbeat with signed receipt)
- **`/unay/*`** — LMDB memory CRUD; provenance-tagged memory store
- **Cortex reasoning** — every inference cites its source in the receipt
- **Wire D** — signing fabric live

## What's Experimental

- **LMDB persistent storage** — functional on HF Spaces with persistent disk enabled; not all deployments have this enabled
- **Embedding model caching** — model weights cache at build time; cold-start may be slow on HF free tier

## What's Deprecated

Nothing deprecated in this repo.

---

*Co-Authored-By: Perplexity Computer Agent*
*Doctrine v11 — 749/14/163 — c7c0ba17*
