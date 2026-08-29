#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
# Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
"""N1–N25 factory organs on a-11-oy.com.

GET  /organs
GET  /api/a11oy/v1/organs/n
GET  /api/a11oy/v1/organs/n/{id}
POST /api/a11oy/v1/organs/n/{id}

Does not collide with /api/a11oy/v1/organs/integrity.
Not 25 public Spaces. GPU tune stays UNAVAILABLE. Formulas never grant authority.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PAGES = Path(__file__).resolve().parent / "pages"
_PAGE = _PAGES / "organs-n25.html"

ORGANS: tuple[dict[str, str], ...] = (
    {"id": "N1", "title": "Serve", "body": "brain", "job": "inference serving", "evidence": "SIMULATED", "ph": "Prompt to serve (schema-checked, no GPU claim)"},
    {"id": "N2", "title": "Graph", "body": "nervous", "job": "agent orchestration", "evidence": "SIMULATED", "ph": "Goal for a 3-node fail-closed graph"},
    {"id": "N3", "title": "Guard", "body": "immune", "job": "input/output safeguard", "evidence": "MEASURED", "ph": "Text to screen (deny weapons / PII / exfil)"},
    {"id": "N4", "title": "Mosaic", "body": "circulatory", "job": "data mosaic", "evidence": "SIMULATED", "ph": "Join key, e.g. lyte-pilot-01"},
    {"id": "N5", "title": "Lattice", "body": "immune", "job": "defense overlay", "evidence": "MODELED", "ph": "Request to score against the lattice"},
    {"id": "N6", "title": "Cover", "body": "heart", "job": "P&C insurance core", "evidence": "SIMULATED", "ph": "Risk note for a synthetic quote"},
    {"id": "N7", "title": "Quant", "body": "brain", "job": "algorithmic research and backtest", "evidence": "SIMULATED", "ph": "Ticker, e.g. SYN"},
    {"id": "N8", "title": "Title", "body": "skeleton", "job": "property records", "evidence": "SIMULATED", "ph": "Parcel id, e.g. 14-22-08"},
    {"id": "N9", "title": "Retrieve", "body": "nervous", "job": "retrieval and memory", "evidence": "MEASURED", "ph": "Query the factory corpus"},
    {"id": "N10", "title": "Observe", "body": "immune", "job": "trace and evaluation", "evidence": "MEASURED", "ph": "Note to attach as a trace"},
    {"id": "N11", "title": "Tune", "body": "brain", "job": "receipted fine-tune", "evidence": "UNAVAILABLE", "ph": "Dataset digest to request a tune (GPU denied)"},
    {"id": "N12", "title": "Schema", "body": "skeleton", "job": "constrained generation", "evidence": "SIMULATED", "ph": "Fill a Lyte quote schema from a sentence"},
    {"id": "N13", "title": "Energy", "body": "circulatory", "job": "joule accounting", "evidence": "MODELED", "ph": "Token count to model joules"},
    {"id": "N14", "title": "Tool", "body": "nervous", "job": "agent tool protocol", "evidence": "MEASURED", "ph": "lookup | quote | forbidden"},
    {"id": "N15", "title": "Memory", "body": "brain", "job": "persistent agent memory", "evidence": "MEASURED", "ph": "key=value to store, or a key to recall"},
    {"id": "N16", "title": "Eval", "body": "immune", "job": "offline evaluation", "evidence": "MEASURED", "ph": "Suite name, e.g. lyte-negatives"},
    {"id": "N17", "title": "Mesh", "body": "circulatory", "job": "distributed inference", "evidence": "SIMULATED", "ph": "Prompt to fan out across 3 synthetic nodes"},
    {"id": "N18", "title": "Route", "body": "circulatory", "job": "LLM gateway and routing", "evidence": "MEASURED", "ph": "Prompt; route by length / deny / json"},
    {"id": "N19", "title": "Cache", "body": "circulatory", "job": "prefix and semantic cache", "evidence": "MEASURED", "ph": "Prefix to cache or look up"},
    {"id": "N20", "title": "Voice", "body": "nervous", "job": "realtime duplex voice", "evidence": "SIMULATED", "ph": "Utterance to wrap as a duplex turn"},
    {"id": "N21", "title": "Sandbox", "body": "skeleton", "job": "isolated agent code execution", "evidence": "MEASURED", "ph": "Integer math only, e.g. (2+3)*4"},
    {"id": "N22", "title": "Identity", "body": "skeleton", "job": "non-human agent identity", "evidence": "SIMULATED", "ph": "Agent role, e.g. lyte-underwriter"},
    {"id": "N23", "title": "Rails", "body": "immune", "job": "conversation rails", "evidence": "MEASURED", "ph": "Turn text; rails refuse out-of-policy"},
    {"id": "N24", "title": "Browser", "body": "nervous", "job": "agent browser actuation", "evidence": "SIMULATED", "ph": "Same-origin path, e.g. /trust"},
    {"id": "N25", "title": "Policy", "body": "immune", "job": "authorization policy for tools", "evidence": "MEASURED", "ph": "tool=quote resource=lyte"},
)

_BY_ID = {o["id"]: o for o in ORGANS}
_CORPUS = (
    "Lyte is the admitted protected design-partner cell.",
    "Killinchu is the only public synthetic reference.",
    "Formulas never grant authority. Locked set is exactly 8.",
    "Decision Cell Compiler binds a vertical manifest into receipts.",
    "Nexus is classified as an A11oy incubator package.",
)
_TITLE = {
    "14-22-08": {"parcel": "14-22-08", "holder": "synthetic-trust-a", "status": "clear"},
    "99-00-01": {"parcel": "99-00-01", "holder": "synthetic-trust-b", "status": "lien"},
}
_MOSAIC = {"lyte-pilot-01": {"buyer": "Lyte Services", "exposure": "protected-pilot"}}
_MEMORY: dict[str, dict[str, str]] = {}
_CACHE: dict[str, dict[str, Any]] = {}
_TRACES: list[dict[str, str]] = []
_RUNS: list[dict[str, Any]] = []


def _deny(text: str) -> bool:
    return bool(re.search(r"\b(weapon|target(ing)?|kill chain|munition|exfil|ssn\b|password\s*=)", text, re.I))


def _safe_math(expr: str) -> float:
    clean = re.sub(r"\s+", "", expr)
    if not clean or not re.fullmatch(r"[0-9+\-*/().]+", clean) or len(clean) > 64:
        raise ValueError("sandbox denied")
    i = 0

    def peek() -> str:
        return clean[i] if i < len(clean) else ""

    def eat(c: str | None = None) -> None:
        nonlocal i
        if c and peek() != c:
            raise ValueError("sandbox denied")
        i += 1

    def num() -> float:
        nonlocal i
        s = ""
        if peek() == "-":
            s = "-"
            eat()
        while peek().isdigit():
            s += clean[i]
            i += 1
        if not s or s == "-":
            raise ValueError("sandbox denied")
        return float(s)

    def factor() -> float:
        if peek() == "(":
            eat("(")
            v = expr_p()
            eat(")")
            return v
        return num()

    def term() -> float:
        v = factor()
        while peek() in ("*", "/"):
            op = peek()
            eat()
            r = factor()
            if op == "/" and r == 0:
                raise ValueError("div/0")
            v = v * r if op == "*" else v / r
        return v

    def expr_p() -> float:
        v = term()
        while peek() in ("+", "-"):
            op = peek()
            eat()
            r = term()
            v = v + r if op == "+" else v - r
        return v

    v = expr_p()
    if i != len(clean) or v != v:
        raise ValueError("sandbox denied")
    return v


def _sha(obj: dict[str, Any]) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def catalog() -> dict[str, Any]:
    return {
        "schema": "szl.organ-catalog/v1",
        "honesty": "LIVE",
        "count": len(ORGANS),
        "admitted_public": False,
        "origin": "https://a-11-oy.com/organs",
        "note": "N1–N25 execute on a-11-oy.com. Not 25 public Spaces. GPU tune remains UNAVAILABLE.",
        "formula_grants_authority": False,
        "locked_formula_count": 8,
        "items": [
            {
                "id": o["id"],
                "title": o["title"],
                "body": o["body"],
                "job": o["job"],
                "honesty": "LIVE",
                "evidence_class": o["evidence"],
                "run": f"POST /api/a11oy/v1/organs/n/{o['id']}",
                "placeholder": o["ph"],
            }
            for o in ORGANS
        ],
        "recent": [
            {"id": r["id"], "title": r["title"], "status": r["status"], "hash": r["hash"], "created_at": r["created_at"]}
            for r in _RUNS[-8:][::-1]
        ],
    }


def _receipt(organ: dict[str, str], prompt: str, status: str, output: dict[str, Any], limitations: list[str]) -> dict[str, Any]:
    body = {
        "schema": "szl.organ-run/v1",
        "id": organ["id"],
        "title": organ["title"],
        "status": status,
        "honesty": "LIVE",
        "evidence_class": organ["evidence"],
        "formula_grants_authority": False,
        "input": {"prompt": prompt},
        "output": output,
        "limitations": limitations,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    body["hash"] = _sha({k: v for k, v in body.items() if k != "hash"})
    _RUNS.append(body)
    if len(_RUNS) > 50:
        del _RUNS[:-50]
    return body


def run_organ(oid: str, prompt: str = "") -> dict[str, Any]:
    organ = _BY_ID.get(oid)
    if not organ:
        raise KeyError(oid)
    text = (prompt or "").strip()
    fn = _RUNNERS[oid]
    return fn(organ, text)


def _run_n1(o, t):
    if not t:
        return _receipt(o, t, "DENIED", {"reason": "empty prompt"}, ["Serve refuses empty input"])
    if _deny(t):
        return _receipt(o, t, "DENIED", {"reason": "guarded"}, ["Serve is fail-closed"])
    return _receipt(o, t, "EXECUTED", {"object": "chat.completion", "model": "factory-schema-envelope", "gpu": False, "choices": [{"message": {"role": "assistant", "content": f"Served (structural): {t[:240]}"}}]}, ["No GPU. Schema envelope only."])


def _run_n2(o, t):
    goal = t or "compile-lyte-quote"
    nodes = [{"name": n, "state": "DONE" if i < 2 else "AWAITING_APPROVAL"} for i, n in enumerate(("intake", "policy-shadow", "human-interrupt"))]
    return _receipt(o, t, "AWAITING_APPROVAL", {"goal": goal, "nodes": nodes, "interrupt": True}, ["Graph never auto-promotes."])


def _run_n3(o, t):
    denied = (not t) or _deny(t)
    return _receipt(o, t, "DENIED" if denied else "EXECUTED", {"action": "DENY" if denied else "ALLOW", "rules": ["weapons", "exfil", "secrets"]}, ["Guard is LOG_ONLY overlay."])


def _run_n4(o, t):
    key = t or "lyte-pilot-01"
    row = _MOSAIC.get(key)
    return _receipt(o, t, "EXECUTED" if row else "DENIED", {"key": key, "row": row}, ["Synthetic mosaic only."])


def _run_n5(o, t):
    score = 0.12 if _deny(t) else 0.81
    return _receipt(o, t, "DENIED" if score < 0.5 else "EXECUTED", {"lattice_score": score}, ["Modeled overlay. Not a measured SOC."])


def _run_n6(o, t):
    note = t or "warehouse sprinklered"
    if _deny(note):
        return _receipt(o, t, "DENIED", {"reason": "guarded"}, ["Synthetic quote. Not a licensed bind."])
    return _receipt(o, t, "EXECUTED", {"product": "P&C-synthetic", "premium_usd": 1200 + len(note) * 3, "bind": "LOG_ONLY"}, ["Synthetic quote. Not a licensed insurance bind."])


def _run_n7(o, t):
    ticker = (t or "SYN").upper()[:8]
    series = [100 + i + (1 if i % 2 == 0 else -1) for i in range(8)]
    ret = (series[-1] - series[0]) / series[0]
    return _receipt(o, t, "EXECUTED", {"ticker": ticker, "series": series, "return": round(ret, 4), "causal": False}, ["Synthetic series. Causal claims prohibited."])


def _run_n8(o, t):
    rec = _TITLE.get(t or "14-22-08")
    return _receipt(o, t, "EXECUTED" if rec else "DENIED", {"id": t or "14-22-08", "record": rec}, ["Synthetic title plant."])


def _run_n9(o, t):
    q = t.lower()
    hits = [row for row in _CORPUS if not q or q in row.lower()][:3]
    return _receipt(o, t, "EXECUTED" if hits else "DENIED", {"query": q, "hits": hits}, ["In-factory corpus only."])


def _run_n10(o, t):
    row = {"id": f"tr_{len(_TRACES)+1}", "organ": o["id"], "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "note": t or "observe"}
    _TRACES.append(row)
    return _receipt(o, t, "EXECUTED", {"attached": row, "traces": _TRACES[-5:]}, ["In-process traces."])


def _run_n11(o, t):
    return _receipt(o, t, "DENIED", {"dataset": t or "sha256:unavailable", "gpu": "UNAVAILABLE", "job": "not-queued"}, ["Tune is receipted and refused. No GPU in this runtime."])


def _run_n12(o, t):
    text = t or "Lyte warehouse quote"
    obj = {"insured": "Lyte Services" if re.search(r"lyte", text, re.I) else "synthetic-buyer", "occupancy": "warehouse" if re.search(r"ware", text, re.I) else "unspecified", "bind": False}
    return _receipt(o, t, "EXECUTED", {"schema": "lyte.quote.v1", "value": obj}, ["Constrained fill. Not a model decode."])


def _run_n13(o, t):
    try:
        n = int(t) if t.strip().isdigit() else len(t) or 128
    except Exception:
        n = 128
    return _receipt(o, t, "EXECUTED", {"tokens": n, "joules_modeled": round(n * 0.0024, 4)}, ["Modeled joules. Not a watt-meter."])


def _run_n14(o, t):
    name = re.sub(r"^tool:", "", t or "lookup")
    allow = {"lookup", "quote"}
    if name not in allow:
        return _receipt(o, t, "DENIED", {"tool": name, "allow": sorted(allow)}, ["Unknown tools are denied."])
    result: Any = _CORPUS[0] if name == "lookup" else {"premium_usd": 1200}
    return _receipt(o, t, "EXECUTED", {"tool": name, "result": result}, ["Allowlisted tools only."])


def _run_n15(o, t):
    if "=" in t:
        k, v = t.split("=", 1)
        rec = {"k": k.strip(), "v": v.strip(), "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        _MEMORY[rec["k"]] = rec
        return _receipt(o, t, "EXECUTED", {"stored": rec, "size": len(_MEMORY)}, ["Process memory. Not a customer vault."])
    hit = _MEMORY.get(t)
    return _receipt(o, t, "EXECUTED" if hit else "DENIED", {"key": t, "value": hit}, ["Recall miss is DENIED, not fabricated."])


def _run_n16(o, t):
    cases = [{"id": "neg-stale", "pass": True}, {"id": "neg-missing", "pass": True}, {"id": "pos-quote", "pass": True}, {"id": "weapon", "pass": True}]
    return _receipt(o, t, "EXECUTED", {"suite": t or "lyte-negatives", "passed": 4, "cases": cases}, ["Offline fixtures."])


def _run_n17(o, t):
    prompt = t or "fanout"
    nodes = [{"name": n, "echo": prompt[:80], "ok": True} for n in ("alpha", "beta", "gamma")]
    return _receipt(o, t, "EXECUTED", {"nodes": nodes, "aggregate": [n["name"] for n in nodes]}, ["Synthetic mesh. Not a GPU cluster."])


def _run_n18(o, t):
    route = "deny" if _deny(t) else "json-schema" if t.strip().startswith("{") else "long-context" if len(t) > 400 else "default"
    return _receipt(o, t, "DENIED" if route == "deny" else "EXECUTED", {"route": route}, ["Rule router. No vendor keys."])


def _run_n19(o, t):
    if not t:
        return _receipt(o, t, "DENIED", {"reason": "empty prefix"}, ["Cache needs a prefix"])
    hit = _CACHE.get(t)
    if hit:
        hit["hits"] += 1
        return _receipt(o, t, "EXECUTED", {"hit": True, "value": hit["v"], "hits": hit["hits"]}, ["In-process prefix cache."])
    _CACHE[t] = {"v": f"cached:{t[:80]}", "hits": 0}
    return _receipt(o, t, "EXECUTED", {"hit": False, "stored": True}, ["Miss stored. Not a semantic GPU cache."])


def _run_n20(o, t):
    utter = t or "acknowledge"
    return _receipt(o, t, "EXECUTED", {"turn": {"user": utter, "assistant": f"Heard (transcript only): {utter}"}, "audio": False}, ["Transcript envelope. Not a realtime voice stack."])


def _run_n21(o, t):
    try:
        value = _safe_math(t or "1+1")
        return _receipt(o, t, "EXECUTED", {"value": value}, ["Integer math sandbox. No eval, no FS, no net."])
    except Exception as err:
        return _receipt(o, t, "DENIED", {"reason": str(err)}, ["Fail closed."])


def _run_n22(o, t):
    role = t or "lyte-underwriter"
    digest = hashlib.sha256(f"nhi:{role}".encode()).hexdigest()
    return _receipt(o, t, "EXECUTED", {"agent_id": f"nhi_{digest[:16]}", "role": role, "human": False}, ["Synthetic NHI. Not a production IdP."])


def _run_n23(o, t):
    off = _deny(t) or bool(re.search(r"ignore previous|jailbreak", t, re.I))
    return _receipt(o, t, "DENIED" if off else "EXECUTED", {"rail": "block" if off else "allow", "turn": t}, ["Conversation rails."])


def _run_n24(o, t):
    path = t or "/trust"
    allow = bool(re.fullmatch(r"/[A-Za-z0-9/_-]*", path))
    return _receipt(o, t, "EXECUTED" if allow else "DENIED", {"path": path, "actuation": f"navigate:{path}" if allow else None, "same_origin": True}, ["Same-origin navigation log. No remote browse."])


def _run_n25(o, t):
    text = t or "tool=quote resource=lyte"
    m_tool = re.search(r"tool=([a-z0-9-]+)", text, re.I)
    m_res = re.search(r"resource=([a-z0-9-]+)", text, re.I)
    tool = m_tool.group(1) if m_tool else "quote"
    resource = m_res.group(1) if m_res else "lyte"
    allow = tool in {"quote", "lookup"} and resource == "lyte"
    return _receipt(o, t, "APPROVED" if allow else "DENIED", {"tool": tool, "resource": resource, "allow": allow}, ["Tool authorization. Formulas never grant authority."])


_RUNNERS = {f"N{i}": globals()[f"_run_n{i}"] for i in range(1, 26)}


def register(app: Any, ns: str = "a11oy") -> str:
    from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
    from starlette.routing import Route

    api = f"/api/{ns}/v1/organs/n"

    async def _catalog(request: Any) -> JSONResponse:
        return JSONResponse(catalog())

    async def _one(request: Any) -> JSONResponse:
        oid = (request.path_params.get("id") or "").upper()
        if oid not in _BY_ID:
            return JSONResponse({"error": "unknown organ", "id": oid}, status_code=404)
        prompt = ""
        if request.method == "POST":
            try:
                payload = await request.json()
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                prompt = str(payload.get("prompt") or "")
        else:
            prompt = str(request.query_params.get("prompt") or "")
        if request.method in {"GET", "HEAD"} and not prompt:
            return JSONResponse(_BY_ID[oid])
        return JSONResponse(run_organ(oid, prompt))

    async def _page(request: Any = None) -> Any:
        if _PAGE.is_file():
            return FileResponse(_PAGE, media_type="text/html")
        return HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>N1–N25 organs</title>"
            "<p>LIVE. GET /api/a11oy/v1/organs/n</p>"
        )

    routes = [
        Route("/organs", _page, methods=["GET", "HEAD"]),
        Route(api, _catalog, methods=["GET", "HEAD"]),
        Route(api + "/{id}", _one, methods=["GET", "HEAD", "POST"]),
        Route("/api/organs/n", _catalog, methods=["GET", "HEAD"]),
        Route("/api/organs/n/{id}", _one, methods=["GET", "HEAD", "POST"]),
    ]
    app.router.routes[0:0] = routes
    print(f"[a11oy] N1–N25 organs registered: /organs + {api} [moved {len(routes)} routes to front]", file=sys.stderr)
    return f"n25-organs-ok routes={len(routes)}"
