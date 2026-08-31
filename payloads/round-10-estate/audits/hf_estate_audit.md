# Hugging Face Estate Audit — SZLHOLDINGS

Collected: 2026-08-30 23:59 UTC · READ_ONLY · via authenticated connector (admin role on org)
Org plan: **team** (paid) · Authenticated account: **betterwithage** (PRO) · Second org: **alloyscape**

## Counts

| Lane | Count | Note |
|---|---|---|
| Models | 43 | public |
| Datasets | 29–37 | REST `full=true` returns 29; connector listing returned 37 — use 29 as conservative floor, enumerate collection to reconcile |
| Spaces | 45 | 28 docker · 16 static · 1 gradio |
| Collections | 18 | incl. Start Here, Canonical Estate, Flagship Models/Spaces |

## Critical gotcha — casing
`api/models?author=szlholdings` (lowercase) returns **zero**. The org is `SZLHOLDINGS`. Any diligence or audit script using the lowercase handle silently concludes the org has no assets. Fix all references to the canonical casing.

## Billing posture (B-06 resolution)
Org is on a **paid team plan** and the user account is **PRO**. The round-9 concern that 28 Docker Spaces would be un-recreatable on free `cpu-basic` is **resolved at current state**. Guard against future downgrade.

## Breakout asset
`killinchu-osint-corpus` — **41,122 downloads, 8 likes**. This is the single most-downloaded object in the estate by ~10x. It is a counter-UAS OSINT corpus. It is the distribution proof. Lead with it.

## Top models
chaski (1,943) · SZL-Khipu-1.5B (1,102) · SZL-Forge-1.5B-ReceiptAgent (954) · SZL-Khipu-1.5B-GGUF (611)

## Org card
`SZLHOLDINGS/README` is pinned, static, and already governed: it states measured truth states dated 2026-08-30 and closes with "Runtime state is not evidence of a deployed revision." It declares the five flagships: a11oy, killinchu, governed-receipt-verifier, szl-atelier, holographic.

## Kernels
NOT_ENUMERABLE_VIA_API. Manual Hub UI inventory required. Do not publish a kernel count without a dated manual pass.

## Private evidence stores (by design)
vault-artifacts · szl-evidence · szl-training-receipts · yuyay-v3-axis-labels-v1 · thesis-formula-index · anatomy-alive-harness · szl-org-infra · legacy-archive
