# Run the 13-axis Yuyay decision gate

**id:** `recipe-yuyay-gate`  
**tags:** yuyay, gate, decision, 13-axis, lambda, aggregate, governance, axis  

## Summary
Evaluate an action against the 13-axis Yuyay gate (Λ aggregator) before Rosie commits to it.

## Steps
1. POST the action context to /v1/yuyay/gate.
2. Λ aggregates the axes (Λ is Conjecture 1 — NOT a proven theorem).
3. Returns pass/fail per axis + aggregate verdict.

## Code
```python
import requests
r = requests.post(BASE+'/v1/yuyay/gate', json={'action':'send_email','axes':{...}})
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._