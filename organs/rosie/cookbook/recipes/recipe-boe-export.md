# Export a Body-of-Evidence bundle

**id:** `recipe-boe-export`  
**tags:** boe, evidence, export, bundle, audit, receipt, compliance, slsa  

## Summary
Produce a signed Body-of-Evidence (BoE) bundle of receipts for an audit or a customer.

## Steps
1. Select the receipts for the window.
2. Bundle + sign (SLSA L1 honest — not L3).
3. Export as a verifiable archive.

## Code
```python
from szl_evidence import export_boe
bundle = export_boe(since='2026-05-01')
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._