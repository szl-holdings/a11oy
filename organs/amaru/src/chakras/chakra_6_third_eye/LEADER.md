# LEADER: modelcontextprotocol/python-sdk

**URL:** https://github.com/modelcontextprotocol/python-sdk  
**License:** MIT  
**License SHA (blob):** `3d48435454b105021b4f777c11b6b07d8d2ffea3`  
**HEAD commit (main):** `161834d4aee2633c42d3976c8f8751b6c4d947d5`  
**Commit date:** 2026-05-08T16:42:44Z

## Why chosen

| Criterion | python-sdk | gorilla |
|---|---|---|
| License | MIT ✓ | Apache-2.0 ✓ |
| Dispatch primitive | `session.call_tool(name, args)` — 1 RPC call | OpenFunctions requires inference server |
| Kernel extractability | Pure Python, sync-wrappable | Coupled to model weights |
| Mockability | `invoke` callable injection trivial | Requires HTTP stub |
| Dependency footprint | `anyio` + `pydantic` | `torch` / vLLM |

**Decision:** python-sdk wins. Its `ToolManager.call_tool(name, args, context)` pattern reduces to a single dict lookup + async run — extractable to ≤10 sync lines with a mockable callable injected at the boundary. gorilla/OpenFunctions is powerful for LLM-driven selection but mandates a model server, violating the kernel-size constraint.

## Dispatch anatomy (from source)

```
src/mcp/client/session.py       → ClientSession.call_tool(name, args)
src/mcp/server/mcpserver/tools/tool_manager.py → ToolManager.call_tool(name, args, ctx)
src/mcp/server/mcpserver/tools/base.py          → Tool.run(args, ctx)
```

Core pattern: `tool = registry[name]; result = tool.fn(**args)`. Everything else is schema validation and async transport — stripped in the kernel.
