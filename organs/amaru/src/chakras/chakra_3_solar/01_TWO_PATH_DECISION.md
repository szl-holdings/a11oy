# Two-Path Decision: vLLM-Distilled vs. llama.cpp-Wrapped

Both paths satisfy the RIMAY kernel contract: `(state, world, features, priors, seed) -> int`.

---

## Path A — vLLM-Distilled (`kernel.py :: propose`)

```python
# ~6 SLOC core logic
import torch
def propose(state, world, features, priors, seed: int) -> int:
    logits = torch.tensor(priors) + torch.tensor(features)
    g = torch.Generator(); g.manual_seed(seed)
    return int(torch.multinomial(torch.softmax(logits, -1), 1, generator=g).item())
```

| Property | Value |
|----------|-------|
| Leader | vllm-project/vllm @ 6548560 (Apache-2.0) |
| Deps | torch only |
| Inference | None — samples over supplied `priors` |
| Determinism | Yes (Generator seed) |
| Replay | Exact |
| Binary required | No |
| SLOC | ≤10 |

**Use when:** development, unit tests, replay audits, CI, any environment
without a compiled llama.cpp binary.  Priors are supplied externally
(distilled, cached, or synthetic); this path just samples them cleanly.

---

## Path B — llama.cpp-Wrapped (`rimay_llamacpp_path.py :: propose`)

| Property | Value |
|----------|-------|
| Leader | ggml-org/llama.cpp @ 253ba110 (MIT) |
| Binding | abetlen/llama-cpp-python ≥0.3 (MIT) |
| Deps | `pip install llama-cpp-python` + compiled .gguf model |
| Inference | Real local LLM inference (llama.cpp engine) |
| Determinism | Yes (set_seed + argmax, no sampling) |
| Replay | Exact given same model weights |
| Binary required | Yes (llama.cpp shared lib inside llama-cpp-python wheel) |
| SLOC | ~40 core logic |

**Use when:** production local inference, offline / air-gapped deployment,
real logit generation from a .gguf model, or when priors cannot be
pre-supplied and must be derived from live model weights.

---

## Decision matrix

| Situation | Use |
|-----------|-----|
| Writing tests, CI, no GPU/model | Path A |
| Replay audit with known priors | Path A |
| Prototyping new RIMAY features | Path A |
| Production inference, local model | Path B |
| Air-gapped / embedded device | Path B |
| Need llama.cpp-specific logits | Path B |
| llama.cpp binary unavailable | Path A (fallback) |

---

## Contract compatibility

Both functions share the identical signature and return type.
Switching paths requires only changing the import:

```python
# Dev / test
from chakra_3_solar.kernel import propose

# Production local inference
from chakra_3_solar.rimay_llamacpp_path import propose
```

No calling code changes needed.

---

## Credits

- Path A leader: [vllm-project/vllm](https://github.com/vllm-project/vllm) — Apache-2.0
- Path B leader: [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) — MIT, commit `253ba110bcd372207ca7b0bb56f1ea10d60d53fd`
- Path B binding: [abetlen/llama-cpp-python](https://github.com/abetlen/llama-cpp-python) — MIT
