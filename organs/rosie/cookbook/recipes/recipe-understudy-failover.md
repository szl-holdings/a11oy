# Promote Rosie as a11oy's understudy

**id:** `recipe-understudy-failover`  
**tags:** understudy, failover, a11oy, promote, health, resilience, aide  

## Summary
Health-check a11oy and, on failure, promote Rosie to serve the same routes (failover understudy).

## Steps
1. GET /api/rosie/v2/understudy/health.
2. On a11oy failure, POST /api/rosie/v2/understudy/promote.
3. Rosie serves the 7-tier router + RAG + MCP locally.

## Code
```python
import requests
requests.post(BASE+'/api/rosie/v2/understudy/promote')
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._