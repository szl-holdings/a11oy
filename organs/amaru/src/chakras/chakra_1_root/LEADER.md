# LEADER: tinygrad

**Chosen leader:** tinygrad  
**Repository URL:** https://github.com/tinygrad/tinygrad  
**Commit SHA:** 1b779a9058b4a9acb12387133e7ded436ae3c0ca  
**License:** MIT  
**License file URL:** https://github.com/tinygrad/tinygrad/blob/1b779a9058b4a9acb12387133e7ded436ae3c0ca/LICENSE  
**License holder:** the tiny corp  

## Absorbed Source

**File:** `tinygrad/device.py`  
**Line range absorbed:** 39–54  

```python
# Lines 39-54 of tinygrad/device.py (MIT licensed)
def get_available_devices(self) -> Iterator[str]:
    for device in ALL_DEVICES:
      with contextlib.suppress(Exception): yield self[device].device
@property
def DEFAULT(self) -> str: return DEV.device or self._select_device
@DEFAULT.setter
def DEFAULT(self, v): raise AttributeError(...)
@functools.cached_property
def _select_device(self) -> str:
    assert (dev:=next((d for d in self._devices if d not in ["DISK","TINYFS","NPY"] and getenv(d)==1), None)) is None, ...
    try:
      device = next(self.get_available_devices())
      os.environ["DEV"] = device
      return device
    except StopIteration as exc: raise RuntimeError("no usable devices") from exc
```

## Why tinygrad was chosen

- **Minimal LOC:** 420-line `device.py` vs BitNet's complex C++ CUDA kernel infrastructure.
- **Cleanest dispatch primitive:** The `get_available_devices` + `_select_device` pattern is a pure iterator-based priority dispatch over a static ordered list — directly translatable to our `PATHS = [...]` + `min(costs)` pattern.
- **MIT license:** Confirmed by reading LICENSE file directly via GitHub API.
- **No transitive complexity:** The core loop (lines 39–54) has zero external deps in our kernel.

## Selection rationale over other candidates

- **BitNet** (MIT): Dispatch lives in C++/CUDA kernel launch wrappers — not cleanly Python-extractable to ≤10 lines without hallucinating function signatures. Evaluated and rejected (see REJECTED.md).
- **vLLM** (Apache-2.0): MoE expert routing is valid license-wise but dispatch logic spans multiple files (`moe_align_block_size`, `topk_softmax`). Could not be honestly minimized to ≤10 lines. Evaluated and rejected (see REJECTED.md).
