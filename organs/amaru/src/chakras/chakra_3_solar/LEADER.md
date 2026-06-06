# LEADER: vllm-project/vllm

| Field | Value |
|---|---|
| Repo | https://github.com/vllm-project/vllm |
| License | Apache-2.0 |
| Commit SHA | 6548560496 0c3dc2ce9dcb6d7e02e65c5acc3321 |
| License file | `/LICENSE` — "Apache License, Version 2.0, January 2004" verified at SHA above |
| Core file read | `vllm/v1/sample/sampler.py` — `Sampler.sample()` lines 235–294 |

## Why chosen

- Apache-2.0 confirmed at HEAD SHA (no HFOIL, no proprietary clause).
- `Sampler.sample()` exposes the cleanest propose loop: greedy path is pure `argmax`; random path seeds `torch.Generator` before `multinomial` — exactly the determinism contract RIMAY requires.
- Single Python file, no C extension needed for the kernel distillation.

## Rejected alternatives

See REJECTED.md.
