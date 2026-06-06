# Check Doctrine v11 constants at runtime

**id:** `recipe-doctrine-check`  
**tags:** doctrine, v11, constants, 749, 14, 163, locked, honest, provenance  

## Summary
Return the locked Doctrine v11 numbers (749/14/163) and locked-at commit so claims stay honest.

## Steps
1. GET the doctrine-runtime constants.
2. Compare any claim against 749 decls / 14 axioms / 163 sorries.
3. locked_at c7c0ba17; Λ = Conjecture 1; SLSA L1 honest.

## Code
```python
from szl_doctrine import constants
c = constants()  # {'version':'v11','declarations':749,'axioms':14,'sorries':163}
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._