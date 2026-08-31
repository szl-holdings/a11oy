#!/usr/bin/env python3
"""Capture the full assembled route table + spa-catchall ordering fingerprint.
Refactor-only proof helper: run before and after to prove parity."""
import sys, json, hashlib, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import serve

def dump():
    rows = []
    catchall_idx = None
    for i, r in enumerate(serve.app.router.routes):
        p = getattr(r, "path", None) or getattr(r, "path_format", None)
        methods = sorted(list(getattr(r, "methods", []) or []))
        name = getattr(r, "name", None)
        endpoint = getattr(r, "endpoint", None)
        endpoint_qual = None
        if endpoint is not None:
            endpoint_qual = f"{getattr(endpoint,'__module__','?')}.{getattr(endpoint,'__qualname__',getattr(endpoint,'__name__','?'))}"
        rows.append({
            "idx": i,
            "path": p,
            "methods": methods,
            "name": name,
            "endpoint": endpoint_qual,
        })
        if p == "/{full_path:path}":
            catchall_idx = i
    # order-sensitive fingerprint: (path, methods) sequence
    seq = [(row["path"], tuple(row["methods"])) for row in rows]
    seq_fp = hashlib.sha256(json.dumps(seq).encode()).hexdigest()
    # order-insensitive set of (path,methods)
    setfp = hashlib.sha256(json.dumps(sorted([json.dumps(s) for s in seq])).encode()).hexdigest()
    return {
        "total": len(rows),
        "catchall_idx": catchall_idx,
        "routes_after_catchall": [rows[j] for j in range(catchall_idx+1, len(rows))] if catchall_idx is not None else [],
        "order_fingerprint": seq_fp,
        "set_fingerprint": setfp,
        "rows": rows,
    }

if __name__ == "__main__":
    out = dump()
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/routes.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print("TOTAL", out["total"], "catchall_idx", out["catchall_idx"],
          "after_catchall", len(out["routes_after_catchall"]))
    print("order_fp", out["order_fingerprint"])
    print("set_fp", out["set_fingerprint"])
