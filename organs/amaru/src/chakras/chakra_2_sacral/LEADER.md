# LEADER: stanfordnlp/dspy

| Field | Value |
|-------|-------|
| URL | https://github.com/stanfordnlp/dspy |
| Commit SHA | da1f0871ec8f34e913ecde7c5ebab473022b9c63 |
| License | MIT |
| License URL | https://github.com/stanfordnlp/dspy/blob/main/LICENSE |
| Source file absorbed | dspy/retrievers/embeddings.py |
| Lines absorbed | 7 (normalize + dot-product cosine pattern from `_batch_forward` and `_rerank_and_predict`) |

## Why DSPy

- MIT license — fully permissive, doctrine-compliant.
- `dspy/retrievers/embeddings.py` implements brute-force cosine similarity for small corpora (< 20 000 items) that maps directly onto our PIRWA + QILLQA stores.
- Core pattern absorbed: normalize embeddings → dot-product → argsort → top-k. Reproduced in 9 lines without any DSPy dependency.
