# Honor a GDPR erasure request

**id:** `recipe-gdpr-erase`  
**tags:** gdpr, erase, delete, privacy, forget, compliance, receipt, ccpa  

## Summary
Erase a user's memory entries and emit a signed deletion receipt (right-to-be-forgotten).

## Steps
1. Identify the subject's memory keys.
2. Tombstone + erase; keep a signed deletion receipt (not the data).
3. Return the receipt as proof.

## Code
```python
from szl_privacy import erase
receipt = erase(subject_id='user-123')
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._