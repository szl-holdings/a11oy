# MINIMIZATION PROOF

## Source vs Kernel

| Metric | tinygrad/device.py (leader) | kernel.py (ours) | Notes |
|---|---|---|---|
| Total LOC | 420 | 10 | wc -l |
| Absorbed LOC | 16 (lines 39–54) | 10 | direct distillation |
| Reduction ratio (total) | — | **42.0×** | 420 ÷ 10 |
| Reduction ratio (absorbed) | — | **1.6×** | 16 ÷ 10 |

## What was kept

| tinygrad concept | Our kernel equivalent |
|---|---|
| `ALL_DEVICES = [...]` | `PATHS = ["CPU","GPU","QUANTIZED","MOE"]` |
| `get_available_devices()` iterator | implicit iteration over `PATHS` dict |
| `next(self.get_available_devices())` first-available | `min(costs, key=costs.__getitem__)` min-energy |
| No energy model (tinygrad picks first live device) | NINA Butler-Volmer `nina(η)` supplies energy cost per path |

## What was added (not from leader)

- NINA Butler-Volmer lambda (5 constants, 1 math expression) — domain-specific extension for energy-aware dispatch.
- `random.Random(seed)` for deterministic η sampling from `world` signal inputs.

## Verification

```
$ wc -l kernel.py
10 kernel.py
```

Every line is either a comment/import, a constant, the NINA formula, or one of the 4 dispatch lines. No padding.
