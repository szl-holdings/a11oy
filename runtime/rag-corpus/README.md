---
license: apache-2.0
tags: [agentic-rag, faiss, bge-base, ouroboros, szl-holdings]
---

# SZLHOLDINGS/rag-corpus-v1 — Agentic-RAG corpus + per-organ FAISS indexes

Doctrine v10/v11. Embedding model: **BAAI/bge-base-en-v1.5** (768-dim).
Built by the agentic-RAG SHIP directive (390_AGENTIC_RAG_FAISS_PER_SPACE).

## Contents
- `corpus.jsonl` — 762 chunks, each `~512 tokens` with fields
  `chunk_id, text, source, title, organ_tag, n_chars, approx_tokens`.
- `indexes/<organ>.faiss` — FAISS `IndexFlatIP` over L2-normalized BGE embeddings
  (inner product == cosine similarity).
- `indexes/<organ>.ids.json` — FAISS row -> chunk_id map.
- `indexes/manifest.json` — model/dim/per-organ vector counts.

## Per-organ index vector counts
{
  "cortex": 679,
  "immune": 12,
  "receipt": 16,
  "gate": 63,
  "nervous": 4,
  "all": 762
}

`all.faiss` = the full corpus (rosie/nervous inherits everything). Each `<organ>.faiss`
contains chunks tagged that organ PLUS cross-cutting `all`-tagged chunks.

## Sources
Thesis v18 chapters · szl-cookbook recipes (README + SKILL) · LUTAR_EVIDENCE.md ·
every Lean theorem/lemma in lutar-lean Lutar/ (name + statement + status) ·
Doctrine v10 + v11 (locked) · Frontier corpus (Pacha-Λ, Khipu-Bekenstein,
Yachay-Khipu Operator, Willow-Λ) · 4 founder LinkedIn public posts · szl-trust E4
governed-loop run (12 receipts).

## Honesty (Doctrine v10/v11)
LLM responses cite chunk IDs. Λ-receipt `signature` field is a **PLACEHOLDER**
(Sigstore CI signing not yet wired). ADDITIVE only.
