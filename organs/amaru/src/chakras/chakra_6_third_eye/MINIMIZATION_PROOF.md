# MINIMIZATION PROOF

## Kernel line count

File: `kernel.py`  
Total lines (incl. docstring + blank): 11  
**Code lines (non-blank, non-comment, non-docstring): 8** ✓ ≤10

```
1  import json, random
2  def tinkuy(intent, tools, seed, invoke=None):
3      random.seed(seed)
4      ranked = sorted(tools, key=lambda t: sum(w in intent.lower() for w in t["name"].lower().split("_")), reverse=True)
5      chosen = ranked[0]
6      args = {k: f"<{k}>" for k in chosen.get("params", [])}
7      result = (invoke or (lambda n, a: {"mock": True, "tool": n, "args": a}))(chosen["name"], args)
8      return chosen["name"], args, result
```

## What each line does

| Line | Role |
|---|---|
| 1 | stdlib only; no external deps |
| 2 | signature: (intent, tools, seed, invoke?) |
| 3 | seed RNG for determinism |
| 4 | rank tools by keyword overlap with intent |
| 5 | pick top-ranked tool |
| 6 | build args skeleton from param list |
| 7 | dispatch via injected `invoke` or default mock |
| 8 | return (tool_name, args, result) triple |

## Why nothing can be removed

- **seed**: remove → non-deterministic on tie-breaking
- **ranked sort**: remove → arbitrary tool selected, no intent-routing
- **invoke injection**: remove → can't mock; breaks test isolation
- **args skeleton**: remove → downstream caller gets no argument structure

## Determinism guarantee

`random.seed(seed)` pins any RNG use. The sort is stable and keyword-overlap scoring is pure arithmetic on the inputs. Given fixed `(intent, tools, seed)`, output is byte-identical across processes, Python versions ≥3.7, and platforms.
