# Sign a payload & get a recall receipt

**id:** `recipe-signed-receipt`  
**tags:** sign, signing, payload, signature, provenance, wire-d, dsse, khipu, receipt, sign a payload  

## Summary
Wrap any JSON payload in a DSSE envelope (HMAC-SHA-256) and return a signed receipt Rosie can replay later.

## Steps
1. POST your payload to /api/rosie/v2/recall or call szl_dsse.sign_payload(payload).
2. Rosie attaches keyid 'szlholdings-cosign' and the KHIPU payload type.
3. Store the returned envelope; verify later with the public-key fingerprint.

## Code
```python
from szl_dsse import sign_payload
env = sign_payload({'action':'note','text':'remember the demo is June 16'})
# env -> {payload, payloadType, signatures:[{keyid:'szlholdings-cosign', sig}]}
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._