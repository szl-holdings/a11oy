# Look up a Codex formula

**id:** `recipe-formula-lookup`  
**tags:** formula, codex, kernel, lambda, f15, bekenstein, aggregate, lookup  

## Summary
Fetch one of the 23 Codex-Kernel formula descriptors (5 Lean-proven, 18 open conjecture).

## Steps
1. GET /api/rosie/v2/cookbook/formulas/F1 .. F23.
2. Each descriptor states proven vs open conjecture honestly.
3. F15/F23 (Bekenstein) = OPEN CONJECTURE/stub.

## Code
```python
import requests
f = requests.get(BASE+'/api/rosie/v2/cookbook/formulas/F1').json()
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._