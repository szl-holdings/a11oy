"""
szl_governed_api.py — the SELLABLE governed-inference surface.

What a buyer calls:
    POST /govern/infer   {"prompt": "...", "vertical": "general", "declared": "PUBLIC"}

What they get back (the product):
    {
      "answer":   "<model output, ONLY if governance decision == allow>",
      "decision": "allow" | "review" | "deny",
      "governance": {                      # from a11oy_vertical_feeds.governed_turn
          "lambda": float,                 # Λ (Conjecture 1 — advisory, never a theorem)
          "lambda_floor": float,
          "lambda_pass": bool,
          "gates": [...],                  # deny-by-default safety gates that fired
          "route": {...},
          "doctrine": {...}
      },
      "receipt": {...},                    # SIGNED, hash-chained Khipu receipt (P5/P6)
      "dsse":    {...},                    # DSSE envelope over the receipt
      "energy": {                          # MEASURED joules for THIS turn, honestly labeled
          "joules": float | None,
          "label": "MEASURED" | "UNAVAILABLE",
          "evidence": {...}
      },
      "honesty": "..."                     # plain-English statement of what is/!is proven
    }

DOCTRINE (non-negotiable, enforced here):
  - Λ is Conjecture 1, never a theorem. Labeled "advisory" everywhere.
  - The answer is returned ONLY if governed_turn decision == "allow".
    On "review"/"deny" we return the governance verdict + receipt and NO answer.
    (Never claim more than is real — the half-state is the only unacceptable outcome.)
  - joules are MEASURED only from the real NVML exporter (meter.a-11-oy.com, live:true,
    sample < METER_FRESH_S old). Otherwise label is UNAVAILABLE and joules is null.
    We NEVER fabricate a joule.
  - The receipt is whatever szl_khipu/szl_dsse actually produced — if signing was
    unavailable, the receipt says so (chain_verified / honesty fields preserved).
"""
from __future__ import annotations

import os
import time
import json
import urllib.request
import urllib.error

# --- the governance IP (merged on main) ---------------------------------------
try:
    import a11oy_vertical_feeds as _avf          # provides governed_turn(...)
except Exception:  # pragma: no cover
    _avf = None

# --- config (env-overridable; honest defaults) --------------------------------
OLLAMA_BASE   = os.environ.get("SZL_OLLAMA_BASE",  "https://gpu.a-11-oy.com")
METER_BASE    = os.environ.get("SZL_METER_BASE",   "https://meter.a-11-oy.com")
MODEL         = os.environ.get("SZL_MODEL",        "llama3.1:8b")
METER_FRESH_S = float(os.environ.get("SZL_METER_FRESH_S", "30"))
HTTP_TIMEOUT  = float(os.environ.get("SZL_HTTP_TIMEOUT", "60"))
# Browser-like UA: Cloudflare 403s the default python-urllib UA.
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"


def _http_json(url: str, payload: dict | None = None, timeout: float = HTTP_TIMEOUT) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": _UA, "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _meter_snapshot() -> tuple[float | None, dict]:
    """Return (cumulative_joules, raw) from the real NVML exporter, or (None, {})."""
    try:
        m = _http_json(METER_BASE + "/", timeout=10)
    except Exception as e:
        return None, {"error": f"meter-unreachable: {e}"}
    ts = m.get("ts")
    fresh = (ts is not None) and (abs(time.time() - float(ts)) <= METER_FRESH_S)
    live = any(
        g.get("live") is True
        for eng in m.get("engines", []) for g in eng.get("gpus", [])
    )
    total = (m.get("totals") or {}).get("joules")
    if fresh and live and isinstance(total, (int, float)):
        return float(total), {"fresh": True, "live": True, "exporter": m.get("exporter"), "ts": ts}
    return None, {"fresh": fresh, "live": live, "exporter": m.get("exporter"), "ts": ts}


def _ollama_generate(prompt: str) -> tuple[str, dict]:
    out = _http_json(OLLAMA_BASE + "/api/generate",
                     {"model": MODEL, "prompt": prompt, "stream": False})
    return out.get("response", ""), {
        "model": out.get("model", MODEL),
        "eval_count": out.get("eval_count"),
        "total_duration_ns": out.get("total_duration"),
    }


def govern_infer(prompt: str, *, vertical: str = "general",
                 declared: str = "PUBLIC", severity: float = 0.0) -> dict:
    """The product. Governance-first, answer only if allowed, honest energy + receipt."""
    if _avf is None or not hasattr(_avf, "governed_turn"):
        return {"decision": "error",
                "honesty": "governance module a11oy_vertical_feeds.governed_turn not importable",
                "answer": None}

    # 1) GOVERN FIRST (Λ + deny-by-default gates + signed receipt). Never skipped.
    g = _avf.governed_turn(vertical, prompt, declared=declared,
                           severity=severity, action_kind="inference")
    decision = g.get("decision", "deny")

    # 2) MEASURE the turn — joules MEASURED only, outside the model call window edges.
    j_before, ev_before = _meter_snapshot()

    answer = None
    gen_meta: dict = {}
    if decision == "allow":
        try:
            answer, gen_meta = _ollama_generate(prompt)
        except Exception as e:
            return {"decision": decision, "answer": None,
                    "governance": _pub_gov(g), "receipt": g.get("receipt"), "dsse": g.get("dsse"),
                    "energy": {"joules": None, "label": "UNAVAILABLE", "evidence": {"gen_error": str(e)}},
                    "honesty": "governance allowed the turn but the GPU backend was unreachable; "
                               "no answer and no joules fabricated."}

    j_after, ev_after = _meter_snapshot()

    # 3) Honest joule join: MEASURED iff both endpoints were fresh+live around the call.
    if j_before is not None and j_after is not None and j_after >= j_before:
        joules = round(j_after - j_before, 3)
        energy = {"joules": joules, "label": "MEASURED",
                  "evidence": {"before": ev_before, "after": ev_after, "source": METER_BASE}}
    else:
        energy = {"joules": None, "label": "UNAVAILABLE",
                  "evidence": {"before": ev_before, "after": ev_after,
                               "note": "no fresh+live NVML delta; joule NOT fabricated"}}

    honesty = {
        "allow":  "Governance allowed the turn; answer returned with a signed receipt. "
                  "Λ is Conjecture 1 (advisory), not a theorem. "
                  + ("Joules MEASURED from real NVML." if energy["label"] == "MEASURED"
                     else "Joules UNAVAILABLE this turn — not fabricated."),
        "review": "Λ below advisory floor — flagged for HUMAN REVIEW. No answer returned. "
                  "Receipt records the verdict.",
        "deny":   "A deny-by-default safety gate fired. No answer returned. Receipt records the denial.",
    }.get(decision, "Unrecognized decision.")

    return {
        "decision": decision,
        "answer": answer,
        "governance": _pub_gov(g),
        "receipt": g.get("receipt"),
        "dsse": g.get("dsse"),
        "generation": gen_meta or None,
        "energy": energy,
        "honesty": honesty,
    }


def _pub_gov(g: dict) -> dict:
    return {
        "lambda": g.get("lambda"),
        "lambda_floor": g.get("lambda_floor"),
        "lambda_pass": g.get("lambda_pass"),
        "lambda_kind": "Conjecture 1 (advisory; NOT a theorem)",
        "gates": g.get("gates"),
        "route": g.get("route"),
        "doctrine": g.get("doctrine"),
    }


# --- register on the a11oy FastAPI app (repo convention) ----------------------
def register(app, ns: str = "a11oy"):  # pragma: no cover
    """Attach the buyer-facing governed-inference surface to the a11oy app.

    Routes (ADDITIVE — no overlap with existing /api/a11oy/* namespaces):
      POST /api/a11oy/v1/govern/infer   {prompt, vertical?, declared?, severity?}
      GET  /api/a11oy/v1/govern/health
      GET  /govern                      (also alias for buyer-facing short URL)
    Honest degrade: if FastAPI import or governance module is missing, returns
    the app unchanged (never raises into import). Follows the same register()
    contract as dev2/devA/devB packs.
    """
    # Use raw Starlette Route objects inserted at the HEAD of app.router.routes —
    # the PROVEN pattern in serve.py (compliance-crosswalk mesh). add_api_route +
    # reorder is fragile against the /api/a11oy/{path:path} Node proxy + SPA
    # catch-all; inserting Route(...) at index 0 deterministically wins.
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse
    except Exception:
        return {"registered": [], "status": "starlette-absent"}

    async def _infer(request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        prompt = (body or {}).get("prompt", "")
        if not prompt:
            return JSONResponse({"error": "missing 'prompt'"}, status_code=400)
        return JSONResponse(govern_infer(
            prompt,
            vertical=body.get("vertical", "general"),
            declared=body.get("declared", "PUBLIC"),
            severity=float(body.get("severity", 0.0)),
        ))

    async def _health(request=None):
        jb, ev = _meter_snapshot()
        return JSONResponse({
            "product": "a11oy Governed Inference",
            "governance": _avf is not None and hasattr(_avf, "governed_turn"),
            "ollama_base": OLLAMA_BASE, "model": MODEL,
            "meter_base": METER_BASE,
            "meter_fresh_live": jb is not None, "meter_evidence": ev,
            "honesty": "Λ is Conjecture 1 (advisory). Answer returned only on decision==allow. "
                       "Joules MEASURED only from real NVML; never fabricated.",
        })

    # Landing page: serve the holographic showcase at /govern and /govern/ (branded domain root)
    try:
        from starlette.responses import FileResponse, HTMLResponse
        import os as _os
        _PAGE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "govern_showcase.html")
        async def _landing(request=None):
            if _os.path.exists(_PAGE):
                return FileResponse(_PAGE, media_type="text/html")
            return HTMLResponse("<h1>a11oy Governed Inference</h1><p>showcase asset missing</p>")
    except Exception:
        _landing = None

    # Register at the FULL /api/a11oy/v1/govern/* path (proven to resolve locally,
    # like /api/a11oy/v1/reason) AND the post-strip /v1/govern/* + short /govern/*
    # forms, so it wins regardless of how the front-door forwards.
    paths = [
        ("/govern",       _landing or _health, ["GET"]),
        ("/govern/",      _landing or _health, ["GET"]),
        ("/api/a11oy/v1/govern/infer",  _infer,  ["POST"]),
        ("/api/a11oy/v1/govern/health", _health, ["GET"]),
        ("/v1/govern/infer",  _infer,  ["POST"]),
        ("/v1/govern/health", _health, ["GET"]),
        ("/govern/infer",  _infer,  ["POST"]),
        ("/govern/health", _health, ["GET"]),
    ]
    registered = []
    for path, fn, methods in paths:
        app.router.routes.insert(0, Route(path, fn, methods=methods))
        registered.append(path)
    return {"registered": registered, "status": "ok"}


# Backward-compat alias
def mount(app):  # pragma: no cover
    register(app)
    return app


if __name__ == "__main__":
    import sys
    p = " ".join(sys.argv[1:]) or "Summarize the doctrine of governed inference in two sentences."
    print(json.dumps(govern_infer(p), indent=2, default=str))
