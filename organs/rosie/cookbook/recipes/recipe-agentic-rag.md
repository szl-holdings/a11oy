# Answer with agentic RAG

**id:** `recipe-agentic-rag`  
**tags:** rag, agentic, retrieve, answer, cite, corpus, grounded  

## Summary
Run agentic retrieval-augmented generation over Rosie's provenanced corpus, citing sources.

## Steps
1. POST the question to /api/rosie/v2/rag/ask.
2. Rosie retrieves + reasons over grounded chunks.
3. Answer includes source citations + SHAs.

## Code
```python
import requests
r = requests.post(BASE+'/api/rosie/v2/rag/ask', json={'q':'what is the Yuyay gate'})
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._