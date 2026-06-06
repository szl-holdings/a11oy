# Ingest a document into memory (WAYRA)

**id:** `recipe-ingest-doc`  
**tags:** ingest, wayra, document, memory, index, embed, provenance  

## Summary
Push a document through WAYRA ingest so Rosie can recall + cite it later with a SHA.

## Steps
1. POST the doc to the WAYRA ingest endpoint.
2. Rosie chunks, embeds, and records SHA-256.
3. The doc becomes recall-able + citable.

## Code
```python
from szl_wayra import ingest
ingest(path='spec.pdf')
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._