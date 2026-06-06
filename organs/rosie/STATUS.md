# STATUS.md — rosie (Aide / Cross-Session Memory)

**Updated:** 2026-06-02
**Doctrine v11 — 749 / 14 / 163 — replay hash c7c0ba17**

> **Doctrine v11 LOCKED — `749 / 14 / 163` at kernel commit `c7c0ba17`.**
> 749 declarations · 14 unique axioms · 163 tracked sorries · 12 MCP tools.
> **Λ = Conjecture 1 — NOT a theorem.** SLSA L1 (honest). Quechua = brand only.
> All flagship citations resolve against this locked snapshot. Doctrine bumps
> require a fresh PR with a new kernel commit hash; the v12/781 work was
> reverted as drift on 2026-06-02 per founder doctrine lock.

HF Space: <https://huggingface.co/spaces/SZLHOLDINGS/rosie>

---

## What's Live

- **HF Space** — rosie is deployed and operational on Hugging Face Spaces
- **`/healthz`** — returns Doctrine v11 numbers and service status
- **`/sign`** — Wire D DSSE signing endpoint
- **`/viz/*`** — Operator console SPA (receipt stream, verdict inspector)
- **Wire C to a11oy** — live; operator verdicts forwarded to governance layer
- **`/api/rosie/v2/chaski/escalate`** — Chaski escalation endpoint, returns signed escalation receipt
- **`/api/rosie/v2/unay/erase`** — GDPR Article 17 erasure surface; returns signed receipt (no PII stored)

## What's Experimental

- **Cross-session memory persistence** — LMDB persistence functional; requires persistent disk enabled in HF Space settings
- **Receipt stream WebSocket** — SSE stream live; WebSocket variant under development

## What's Deprecated

Nothing deprecated in this repo.

---

*Co-Authored-By: Perplexity Computer Agent*
*Doctrine v11 — 749/14/163 — c7c0ba17*
