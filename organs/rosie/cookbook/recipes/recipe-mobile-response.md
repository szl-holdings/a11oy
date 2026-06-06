# Adapt a response mobile-first

**id:** `recipe-mobile-response`  
**tags:** mobile, mobile-first, format, responsive, adapt, ui, aide  

## Summary
Format Rosie's answer per SZL_MOBILE_FIRST_STANDARD.md — short blocks, thumb-reachable actions.

## Steps
1. Detect viewport / client hint.
2. Chunk long answers into <=3-line blocks.
3. Surface primary action as a single tap.

## Code
```python
from szl_mobile import adapt
out = adapt(answer, viewport='mobile')
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._