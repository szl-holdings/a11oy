# Route a prompt across the 7-tier open stack

**id:** `recipe-route-llm`  
**tags:** llm, route, router, open-stack, model, inference, tier  

## Summary
Send a prompt through Rosie's 7-tier LLM router (Llama/Qwen/DeepSeek/Mistral/Gemma/Phi/Yi + more).

## Steps
1. POST {'prompt':...} to /api/rosie/v2/llm/route.
2. Router picks a tier by cost/latency/capability.
3. Returns completion + which model served it.

## Code
```python
import requests
r = requests.post(BASE+'/api/rosie/v2/llm/route', json={'prompt':'summarize'})
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._