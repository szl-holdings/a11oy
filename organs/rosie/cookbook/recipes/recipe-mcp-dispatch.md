# Dispatch a Hatun-MCP tool

**id:** `recipe-mcp-dispatch`  
**tags:** mcp, tool, dispatch, hatun, mesh, call, catalog  

## Summary
Call one of the 16 Hatun-MCP tools via the tool mesh, with a signed call receipt.

## Steps
1. GET /api/rosie/v2/cookbook/mcp-tools for the 16-tool catalog.
2. POST the tool name + args to the mesh.
3. Receive result + signed call receipt.

## Code
```python
import requests
tools = requests.get(BASE+'/api/rosie/v2/cookbook/mcp-tools').json()
```

---
_Cherry-picked from the SZL monorepo for Rosie's runtime cookbook. Apache-2.0. Yachay <yachay@szlholdings.dev>; Co-Authored-By: Perplexity Computer Agent. Doctrine v11 (749/14/163)._