# Screen user input for prompt injection

**id:** `recipe-injection-screen`  
**tags:** injection, detect, prompt, filter, sentra, security, immune, guard, screen  

## Summary
Run input through the Sentra immune filter before dispatch; block/warn/allow with reasons + receipt.

## Steps
1. Rosie routes every command through szl_sentra_client POST sentra:/sentra/rosie/filter.
2. verdict=block -> HTTP 403; warn -> proceed + record reasons; allow -> proceed.
3. Fails open (never crashes dispatch) if Sentra unreachable.

## Code
```python
from szl_sentra_client import filter_payload
v = filter_payload({'text': user_input})
if v['verdict']=='block': raise PermissionError(v['reasons'])
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._