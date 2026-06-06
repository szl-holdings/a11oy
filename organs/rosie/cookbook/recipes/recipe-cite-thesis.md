# Cite a thesis chapter with SHA

**id:** `recipe-cite-thesis`  
**tags:** thesis, cite, citation, chapter, sha, ouroboros, v18, v20, v21, puriq, ayni  

## Summary
Pull chapter content from an ingested thesis plus its PDF SHA-256 and a signed recall receipt.

## Steps
1. GET /api/rosie/v2/theses to list (each with pdf_sha256).
2. GET /api/rosie/v2/theses/ouroboros-v18?cite=true for chapters + lean_citations + receipt.
3. Quote the chapter; the SHA proves which document version you cited.

## Code
```python
import requests
t = requests.get(BASE+'/api/rosie/v2/theses/ouroboros-v18?cite=true').json()
ch5 = [c for c in t['chapters'] if c['label']=='5'][0]
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._