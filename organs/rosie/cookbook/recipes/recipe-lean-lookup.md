# Look up a Lean theorem's type signature

**id:** `recipe-lean-lookup`  
**tags:** lean, theorem, proof, type, signature, yuyay_axis, axis, lambda, lutar, verify  

## Summary
Substring-search the 870-declaration Lean index; returns name, kind, status (PROVEN/SORRY/AXIOM), file, signature.

## Steps
1. GET /api/rosie/v2/lean-index?q=axis to search by name substring.
2. Each hit carries kind + status + file:line + the type signature head.
3. Honest: Λ-related results are Conjecture 1, not theorems; SORRY decls flagged.

## Code
```python
import requests
r = requests.get(BASE+'/api/rosie/v2/lean-index', params={'q':'axis'}).json()
for d in r['matches'][:5]: print(d['name'], d['status'])
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._