# Verify a DSSE envelope

**id:** `recipe-verify-envelope`  
**tags:** verify, dsse, envelope, signature, validate, provenance, receipt  

## Summary
Validate an HMAC-SHA-256 DSSE envelope from amaru/sentra/rosie against the public-key fingerprint.

## Steps
1. Paste the envelope JSON.
2. Rosie recomputes the PAE + HMAC.
3. Returns valid/invalid + keyid + fingerprint.

## Code
```python
from szl_dsse import verify
ok = verify(envelope)  # True/False
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._