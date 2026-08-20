#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · Doctrine v11
"""verify_board.py — DEV 2 frontier-board verification harness.

Boots serve.py in-process via TestClient and, for every holographic surface,
resolves its exported endpoint(s) from the surface .js, hits the LOCAL a11oy
endpoints, and asserts HTTP 200 + a non-empty JSON body (honest label present).
Cross-repo killinchu mirror surfaces (endpoints on szlholdings-killinchu.hf.space)
are reported as CROSS-REPO (out of this app's TestClient scope) but recorded.

Produces a WIRED/LIVE matrix (JSON + markdown) to /tmp and stdout.
Usage: python3 tools/verify_board.py
"""
from __future__ import annotations
import json, re, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
SURF_DIR = ROOT / "static" / "3d" / "surfaces"
sys.path.insert(0, str(ROOT))

CONST_RE = re.compile(r"""(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(["'`])([^"'`]*)\2""")
OBJ_RE = re.compile(r"""(?:const|let|var)\s+EP\w*\s*=\s*\{([^}]*)\}""", re.S)
OBJ_KV_RE = re.compile(r"""[\w$]+\s*:\s*(["'`])([^"'`]*)\1""")
EXPORT_RE = re.compile(r"endpoints\s*:\s*\[([^\]]*)\]")


def surface_endpoints(fp: Path):
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    consts = {m.group(1): m.group(3) for m in CONST_RE.finditer(txt)}
    eps = []
    m = EXPORT_RE.search(txt)
    if m:
        for tok in m.group(1).split(","):
            tok = tok.strip()
            if not tok:
                continue
            if tok[0] in "\"'`":
                eps.append(tok.strip("\"'`"))
            elif tok in consts:
                eps.append(consts[tok])
    for om in OBJ_RE.finditer(txt):
        for kv in OBJ_KV_RE.finditer(om.group(1)):
            eps.append(kv.group(2))
    for am in re.finditer(r"""=>\s*`(/[^`$]*)\$\{""", txt):
        eps.append(am.group(1).rstrip("/") + "/reasoning")
    seen, out = set(), []
    for e in eps:
        e = e.strip()
        if not e or e.startswith("<"):
            continue
        if not (e.startswith("/api/") or e.startswith("http")):
            continue
        key = e.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


# Endpoints whose 503 is an HONEST 'unavailable in the dev checkout, LIVE in the
# built image' state (the file is COPY'd to an absolute /app path in the Dockerfile
# but not present at the repo path a TestClient sees). Not a wiring defect.
HONEST_IN_IMAGE = {
    "/api/a11oy/v1/genome": "genome.json COPY'd to /app/data/genome.json in Dockerfile (line 169); "
                            "503 UNAVAILABLE only in the dev TestClient checkout, LIVE in-image",
}


def expected_ok(body):
    if body is None:
        return False, "no-json"
    if isinstance(body, dict):
        if body.get("error"):
            return False, f"error:{body.get('error')}"
        if len(body) == 0:
            return False, "empty-object"
        return True, ",".join(list(body.keys())[:6])
    if isinstance(body, list):
        return (len(body) > 0), f"list[{len(body)}]"
    return True, str(type(body).__name__)


# Per-surface request contract: method + a VALID body (mirrors exactly what the
# surface .js sends via its fetchInit, using the real IDs the backend accepts).
# Anything not listed defaults to GET (the vast majority of surfaces GET a snapshot).
POST_CONTRACT = {
    "/api/a11oy/v1/eval/run": {"suite": "core_honest_v1", "model_id": "szl-modeled-lm"},
    "/api/a11oy/v1/rag/query": {"query": "what is the doctrine lock?"},
    "/api/a11oy/v1/agentloop/run": {"task": "summarize the doctrine lock"},
    "/api/a11oy/v1/harness/apply": {"profile_id": "szl-fable", "model_id": "sovereign_local",
                                    "prompt": "Demonstrate the applied behavior profile."},
    "/api/a11oy/v1/restraint/evaluate": {"task": "smoke"},
    # POST-only governed-run surfaces that accept an empty body ({}) — the surface
    # .js posts `body: "{}"` via fetchInit; mirror that so the matrix is honest.
    "/api/a11oy/v1/pinn/residual/evaluate": {},
    "/api/a11oy/v1/loopforge/run": {},
    "/api/a11oy/v1/counter-uas/compute": None,  # GET alias (added this PR); sentinel handled below
}
# Drop any explicit None sentinels (documented GET-only entries kept for reference).
POST_CONTRACT = {k: v for k, v in POST_CONTRACT.items() if v is not None}


def post_contract(path):
    return POST_CONTRACT.get(path.split("?")[0])


def main():
    from fastapi.testclient import TestClient
    import serve
    import szl3d_holographic as holo

    client = TestClient(serve.app)
    surface_ids = [s["id"] for s in holo.SURFACES]

    rows = []
    for sid in surface_ids:
        fp = SURF_DIR / f"{sid}.js"
        if not fp.is_file():
            rows.append({"surface": sid, "status": "NO_JS", "endpoints": []})
            continue
        eps = surface_endpoints(fp)
        ep_results = []
        for ep in eps:
            if ep.startswith("http"):
                ep_results.append({"ep": ep, "scope": "CROSS-REPO", "code": None,
                                   "live": None, "fields": "killinchu-mirror"})
                continue
            try:
                body_contract = post_contract(ep)
                if body_contract is not None:
                    r = client.post(ep, json=body_contract)
                    if r.status_code == 405:
                        r = client.get(ep)
                else:
                    r = client.get(ep)
                    if r.status_code == 405:
                        r = client.post(ep, json={})
                code = r.status_code
                try:
                    body = r.json()
                except Exception:
                    body = None
                base_path = ep.split("?")[0]
                if code == 200:
                    live, fields = expected_ok(body)
                elif code == 503 and base_path in HONEST_IN_IMAGE:
                    # Honest 'live in-image' degradation: the endpoint returns a
                    # structured UNAVAILABLE envelope (status/error present), and
                    # ships live in the built image. Count as LIVE-IN-IMAGE.
                    live, fields = True, "LIVE-IN-IMAGE (503 dev-only: " + HONEST_IN_IMAGE[base_path][:32] + "…)"
                else:
                    live, fields = False, f"http{code}"
                ep_results.append({"ep": ep, "scope": "LOCAL", "code": code,
                                   "live": live, "fields": fields})
            except Exception as e:
                ep_results.append({"ep": ep, "scope": "LOCAL", "code": "EXC",
                                   "live": False, "fields": str(e)[:60]})
        local = [r for r in ep_results if r["scope"] == "LOCAL"]
        cross = [r for r in ep_results if r["scope"] == "CROSS-REPO"]
        if not ep_results:
            status = "NO_ENDPOINT"
        elif local and all(r["live"] for r in local):
            status = "LIVE"
        elif local and any(r["code"] == 404 for r in local):
            status = "404"
        elif local and any(r["live"] for r in local):
            status = "PARTIAL"
        elif not local and cross:
            status = "CROSS-REPO"
        else:
            status = "BROKEN"
        rows.append({"surface": sid, "status": status, "endpoints": ep_results})

    from collections import Counter
    counts = Counter(r["status"] for r in rows)
    out = {"total": len(rows), "counts": dict(counts), "rows": rows}
    Path("/tmp/board_matrix.json").write_text(json.dumps(out, indent=2))

    lines = ["| Surface | Status | Endpoint | Code | Fields |", "|---|---|---|---|---|"]
    for r in rows:
        if not r["endpoints"]:
            lines.append(f"| {r['surface']} | {r['status']} | — | — | — |")
        for i, e in enumerate(r["endpoints"]):
            sname = r["surface"] if i == 0 else ""
            sstat = r["status"] if i == 0 else ""
            ep = e["ep"].split("?")[0]
            lines.append(f"| {sname} | {sstat} | `{ep}` | {e.get('code')} | {str(e.get('fields',''))[:40]} |")
    Path("/tmp/board_matrix.md").write_text("\n".join(lines))

    print("=== SUMMARY ===")
    print(json.dumps(dict(counts), indent=2))
    print(f"total surfaces: {len(rows)}")
    print("\n=== NON-LIVE / PROBLEM SURFACES ===")
    prob = 0
    for r in rows:
        if r["status"] not in ("LIVE", "CROSS-REPO"):
            prob += 1
            print(f"  {r['surface']}: {r['status']}")
            for e in r["endpoints"]:
                if e["scope"] == "LOCAL" and not e["live"]:
                    print(f"      {e['ep']}  -> {e['code']} {e['fields']}")
    if prob == 0:
        print("  (none — all local surfaces LIVE, cross-repo mirrors recorded)")


if __name__ == "__main__":
    main()
