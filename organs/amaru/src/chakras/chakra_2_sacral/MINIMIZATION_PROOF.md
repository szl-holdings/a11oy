# MINIMIZATION PROOF

## Source

| | Lines |
|-|-------|
| Leader source (`dspy/retrievers/embeddings.py`) | 261 |
| `kernel.py` | 9 |

## LOC Ratio

```
9 / 261 = 0.0345  →  3.45% of source absorbed
```

Reduction factor: **29×**

## What was dropped

- FAISS index construction and approximate search (~80 lines)
- Unbatchify / async batching wrapper (~40 lines)
- DSPy `Prediction` return type and dspy import chain (~30 lines)
- `__init__` configuration surface area (~25 lines)
- Docstrings, type annotations, error handling (~50 lines)
- All external dependency guards (~20 lines)

## What was kept (core pattern)

1. `np.random.default_rng(seed)` — deterministic query vector (stand-in for real encoder)
2. Cosine similarity via `dot / (norm * norm)` — identical to DSPy normalize-then-dot pattern
3. `sorted(..., reverse=True)[:k]` — top-k selection
4. Dual-store pass: PIRWA features first, QILLQA codex priors (capped at 8) second
