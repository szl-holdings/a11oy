# STATUS.md — sentra (Immune System)

**Updated:** 2026-06-02
**Doctrine v11 — 749 / 14 / 163 — replay hash c7c0ba17**

HF Space: <https://huggingface.co/spaces/SZLHOLDINGS/sentra>

---

## What's Live

- **HF Space** — sentra is deployed and operational on Hugging Face Spaces
- **`/healthz`** — returns Doctrine v11 numbers and service status
- **`/sign`** — Wire D DSSE signing endpoint
- **8-gate policy evaluation** — all gates (identity, scope, rate, policy, egress, threat, provenance, replay) active
- **Egress inspector** — outbound traffic evaluated before egress
- **Wire B to a11oy** — live; verdicts forwarded to governance layer
- **Tripwires** — anomalous egress detection active

## What's Experimental

- **Gate_7 replay detection** — functional; full Khipu-chain replay harness integration under development
- **Rate limiter** — gate_2 rate limits are configurable; default thresholds are conservative estimates, not load-tested

## What's Deprecated

Nothing deprecated in this repo.

---

*Co-Authored-By: Perplexity Computer Agent*
*Doctrine v11 — 749/14/163 — c7c0ba17*
