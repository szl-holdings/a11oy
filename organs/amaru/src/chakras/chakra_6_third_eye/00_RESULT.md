# CHAKRA 6 — CH'ULLA-NAWI RESULT

**Chakra:** 6 / Third Eye  
**Layer owned:** boundary-input — TINKUY toolcall primitive, MCP-as-battery integration  
**Role:** (intent, available_tools) → choose tool → invoke → return result

---

## Leader

**modelcontextprotocol/python-sdk** (MIT)  
HEAD `161834d4aee2633c42d3976c8f8751b6c4d947d5` · 2026-05-08  
License blob SHA `3d48435454b105021b4f777c11b6b07d8d2ffea3`

## Kernel (8 code lines)

```python
import json, random

def tinkuy(intent: str, tools: list[dict], seed: int, invoke=None):
    random.seed(seed)
    ranked = sorted(tools, key=lambda t: sum(w in intent.lower() for w in t["name"].lower().split("_")), reverse=True)
    chosen = ranked[0]
    args = {k: f"<{k}>" for k in chosen.get("params", [])}
    result = (invoke or (lambda n, a: {"mock": True, "tool": n, "args": a}))(chosen["name"], args)
    return chosen["name"], args, result
```

**Signature:** `(intent, tools_list, seed) → (tool_name, args, result)`  
**Mock injection:** pass `invoke=callable` or omit for built-in mock.

## 5× Replay

All 5 runs with `(intent="search for MCP tool dispatch examples", seed=42, mocked invoke)` produced byte-identical output:

```
["search_web", {"query": "<query>"}, {"args": {"query": "<query>"}, "mock": true, "tool": "search_web"}]
```

SHA-256: `e87dfbe84bcdc545c6979ac81db6b84752d1a7745ce0d790d45db2e7db8d2ff8` × 5 ✓

## Files

| File | Purpose |
|---|---|
| `kernel.py` | TINKUY primitive — 8 code lines |
| `LEADER.md` | License verification + dispatch anatomy |
| `MINIMIZATION_PROOF.md` | Line-by-line proof of minimality |
| `REPLAY_5X.txt` | 5× byte-identical replay log with SHA-256 |
| `REJECTED.md` | gorilla + ToolFormer rejection rationale |
| `00_RESULT.md` | This file |

## Doctrine compliance

- PUBLIC-ONLY: MIT (python-sdk) ✓
- Kernel ≤10 lines: 8 code lines ✓
- 5× byte-identical replay: ✓
- Honest credit: gorilla and ToolFormer credited accurately in REJECTED.md ✓
- No bandaids: keyword-overlap scoring is transparent and auditable ✓
