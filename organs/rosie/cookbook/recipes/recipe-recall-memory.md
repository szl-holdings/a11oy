# Recall a past conversation or note

**id:** `recipe-recall-memory`  
**tags:** recall, memory, conversation, remember, retrieve, note, provenance, aide  

## Summary
Cosine recall over Rosie's provenanced memory; returns the best match with a signed recall receipt.

## Steps
1. POST {'query':'...'} to /api/rosie/v2/recall.
2. Rosie embeds the query (hashing embedder), scores cosine x kind-weight + tag-match bonus.
3. Top hit returned with a signed recall receipt for replay/audit.

## Code
```python
import requests
r = requests.post(BASE+'/api/rosie/v2/recall', json={'query':'how do I sign a payload'})
print(r.json()['top']['id'])  # -> recipe-signed-receipt
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._