# Chakra 3 — Solar Plexus — CH'ULLA-RIMAY
## L3 Propose Layer: Recon Complete

### Leader
**vllm-project/vllm** @ `6548560496` — Apache-2.0 confirmed.  
Source: `vllm/v1/sample/sampler.py` → `Sampler.sample()`

### Kernel (≤10 lines)
```python
import torch

def propose(state, world, features, priors, seed: int) -> int:
    logits = torch.tensor(priors, dtype=torch.float32)
    logits = logits + torch.tensor(features, dtype=torch.float32)
    g = torch.Generator(); g.manual_seed(seed)
    probs = torch.softmax(logits, dim=-1)
    return int(torch.multinomial(probs, 1, generator=g).item())
```
7 executable lines. Input: `(state, world, features, priors, seed)`. Output: `int` token proposal.

### Replay
5× runs with `seed=42`, fixed features/priors → all returned `1`. Byte-identical: **TRUE**.

### Files
| File | Purpose |
|---|---|
| `kernel.py` | The ≤10 line propose kernel |
| `LEADER.md` | Chosen leader, SHA, license proof |
| `MINIMIZATION_PROOF.md` | Derivation from source + determinism argument |
| `REPLAY_5X.txt` | 5× identical run log |
| `REJECTED.md` | Why llama.cpp and TGI were not chosen |

### Doctrine compliance
- PUBLIC-ONLY: Apache-2.0 ✓
- Kernel ≤10 lines: ✓ (7 lines)
- Byte-identical 5× replay: ✓
- Honest credit: vllm sampler cited at SHA ✓
- No bandaids / no hallucinated APIs: ✓
