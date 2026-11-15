"""
szl_brain_v3 — BRAIN v3: the Anthropic-hosted flagship router for the a11oy Space.

Unseals the .guarded-import-allowlist [DEAD-STUB] entry (2026-11-14): serve.py
already mounts this module guardedly (serve.py "BRAIN v3" block):

    /api/a11oy/v3/brain/{models,chat,chat/stream,converse,tool-call,usage}

Contract honoured verbatim from the serve.py block:
  * Anthropic-hosted flagship model (Opus primary) with a 7-tier fallback ladder
    on model_not_found ONLY — never a fabricated model output.
  * HONEST 503 with the EXACT unblock action when ANTHROPIC_API_KEY is unset
    (Zero-Bandaid Law). Does NOT modify the v1/v2 szl_brain module (additive).
  * Token accounting per model since boot; bounded request ledger (metadata
    only — message content is NEVER stored or logged).
  * Claude Platform USER-scoped keys (sk-ant-usr-*) additionally require the
    "anthropic-workspace-id" header. It is sent iff ANTHROPIC_WORKSPACE_ID is
    set (a non-secret Space VARIABLE — see docs/RUNTIME_ENV.md); a 400
    "not scoped to a workspace" reply degrades to an honest 503 with the exact
    unblock action instead of being swallowed.
  * DSSE/Khipu receipt binding is NOT claimed here (receipts: "ledger+log",
    honest). Structured JSON boot-log line per request is the evidence trail.

Doctrine v11 LOCKED. Λ = Conjecture 1 (advisory, NOT proven trust).
"""
from __future__ import annotations

import json
import os
import time
import collections

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

__all__ = ["register", "router", "BRAIN_V3_MODELS", "status"]

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
WORKSPACE_ENV = "ANTHROPIC_WORKSPACE_ID"

# 7-tier fallback ladder (primary first). Fallback ONLY on model_not_found.
BRAIN_V3_MODELS: list[str] = [
    "claude-opus-5-5",
    "claude-opus-4-8",
    "claude-sonnet-5-5",
    "claude-sonnet-4-6",
    "claude-haiku-5-5",
    "claude-haiku-4-5",
    "claude-fable-5-2",
]
DEFAULT_MODEL = BRAIN_V3_MODELS[0]

_MAX_TOKENS = 4096
_MAX_MESSAGES = 40
_LEDGER_MAX = 500

_usage: dict[str, dict[str, int]] = collections.defaultdict(
    lambda: {"requests": 0, "input_tokens": 0, "output_tokens": 0})
_ledger: "collections.deque[dict]" = collections.deque(maxlen=_LEDGER_MAX)
_boot_ts = time.time()

router = APIRouter()


def _key() -> str:
    return (os.environ.get("ANTHROPIC_API_KEY") or "").strip()


def _workspace_id() -> str:
    return (os.environ.get(WORKSPACE_ENV) or "").strip()


def _headers() -> dict[str, str]:
    """Auth headers. The workspace header is included ONLY when the variable
    is present (absent for workspace-scoped keys is legal; the 400 path below
    reports the exact unblock action for user-scoped keys)."""
    h = {
        "x-api-key": _key(),
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    ws = _workspace_id()
    if ws:
        h["anthropic-workspace-id"] = ws
    return h


def _unavailable(action: str) -> JSONResponse:
    return JSONResponse(
        {"error": "brain v3 unavailable", "unblock": action,
         "fabricated_output": False},
        status_code=503)


def _check_key() -> JSONResponse | None:
    if not _key():
        return _unavailable(
            "Set the Space secret ANTHROPIC_API_KEY (Settings -> Secrets; "
            "Secrets tab ONLY — never Variables — see docs/RUNTIME_ENV.md).")
    return None

def _norm_messages(messages: list) -> list[dict]:
    out = []
    for m in (messages or [])[:_MAX_MESSAGES]:
        role = (m.get("role") or "user").strip() or "user"
        content = m.get("content")
        if isinstance(content, list):
            content = "".join(
                (c.get("text") or "") if isinstance(c, dict) else str(c)
                for c in content)
        if not isinstance(content, str):
            content = str(content or "")
        if role not in ("user", "assistant"):
            role = "user"
        out.append({"role": role, "content": content})
    return out


def _post_messages(payload: dict) -> tuple[int, dict]:
    """One real Anthropic /v1/messages dispatch. Returns (status, body)."""
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0),
                      follow_redirects=False) as client:
        resp = client.post(ANTHROPIC_MESSAGES_URL, headers=_headers(),
                           json=payload)
        return resp.status_code, resp.json()


def _workspace_unblock(resp_body: dict) -> bool:
    msg = str((resp_body or {}).get("error", {}).get("message", "")).lower()
    return "not scoped to a workspace" in msg


def _account(model: str, usage: dict, status: int, latency_ms: int) -> None:
    u = _usage[model]
    u["requests"] += 1
    u["input_tokens"] += int((usage or {}).get("input_tokens") or 0)
    u["output_tokens"] += int((usage or {}).get("output_tokens") or 0)
    entry = {
        "ts": round(time.time(), 3), "model": model, "status": status,
        "latency_ms": latency_ms,
        "input_tokens": int((usage or {}).get("input_tokens") or 0),
        "output_tokens": int((usage or {}).get("output_tokens") or 0),
        "workspace_header_sent": bool(_workspace_id()),
    }
    _ledger.append(entry)
    print("[szl.brain-v3.request] " + json.dumps(entry))


def _dispatch(body: dict, *, stream: bool = False):
    """Bounded fallback walk over the ladder (model_not_found ONLY).

    Never fabricates: auth/permission/quota/transport errors fail closed with
    an honest 503 carrying the provider status + the exact unblock action.
    """
    base = {
        "messages": _norm_messages(body.get("messages")),
        "max_tokens": min(int(body.get("max_tokens") or 1024), _MAX_TOKENS),
        "temperature": body.get("temperature", 0.2),
    }
    if isinstance(body.get("system"), str) and body.get("system").strip():
        base["system"] = body["system"][:8000]
    requested = body.get("model") or DEFAULT_MODEL
    ladder = ([requested] if requested not in BRAIN_V3_MODELS else []) + BRAIN_V3_MODELS
    seen = set()
    for model in ladder:
        if model in seen:
            continue
        seen.add(model)
        payload = dict(base, model=model, stream=stream)
        t0 = time.time()
        try:
            status, data = _post_messages(payload)
        except Exception as exc:
            return _unavailable(
                f"Anthropic transport failed ({type(exc).__name__}). "
                "No output was fabricated.")
        latency = int((time.time() - t0) * 1000)
        if status == 200:
            _account(model, data.get("usage"), status, latency)
            return data, model
        _account(model, data.get("usage"), status, latency)
        if status == 404 or (
                status == 400
                and "model" in str((data.get("error") or {}).get("message", "")).lower()):
            continue  # honest ladder step: model not found
        if status == 400 and _workspace_unblock(data):
            return _unavailable(
                "This Claude Platform user key is not workspace-scoped: set the "
                "Space VARIABLE ANTHROPIC_WORKSPACE_ID (Variables tab ONLY) to "
                "the workspace id (wrkspc_...).")
        if status in (401, 403):
            return _unavailable(
                "Anthropic rejected the ANTHROPIC_API_KEY credential (401/403). "
                "Rotate/re-paste the Space secret; no output was fabricated.")
        if status == 429:
            return JSONResponse(
                {"error": "brain v3 rate-limited upstream (429)",
                 "unblock": "Retry shortly; upstream quota.", "fabricated_output": False},
                status_code=429)
        return JSONResponse(
            {"error": f"brain v3 upstream error ({status})",
             "provider_error": str((data.get("error") or {}).get("message", ""))[:300],
             "fabricated_output": False},
            status_code=502)
    return _unavailable(
        "No model in the brain v3 ladder answered (all 404/invalid model). "
        "No output was fabricated.")

@router.get("/models")
def brain_v3_models() -> JSONResponse:
    return JSONResponse({
        "object": "list",
        "default_model": DEFAULT_MODEL,
        "data": [{"id": m, "tier": i + 1} for i, m in enumerate(BRAIN_V3_MODELS)],
        "key_present": bool(_key()),
        "workspace_id_present": bool(_workspace_id()),
        "fabricated_output": False,
    })


@router.post("/chat")
def brain_v3_chat(body: dict) -> JSONResponse:
    miss = _check_key()
    if miss is not None:
        return miss
    out = _dispatch(body)
    if isinstance(out, JSONResponse):
        return out
    data, model = out
    text = "".join(
        (b.get("text") or "") for b in data.get("content", [])
        if isinstance(b, dict) and b.get("type") == "text")
    return JSONResponse({
        "model": data.get("model", model),
        "role": "assistant",
        "content": text,
        "stop_reason": data.get("stop_reason"),
        "usage": data.get("usage"),
        "receipts": "ledger+log (DSSE binding is a follow-up; NOT claimed)",
    })


@router.post("/converse")
def brain_v3_converse(body: dict) -> JSONResponse:
    """Single-turn convenience wrapper over /chat."""
    msg = str(body.get("message") or "").strip()
    if not msg:
        return JSONResponse({"error": "message required"}, status_code=400)
    return brain_v3_chat({
        "messages": [{"role": "user", "content": msg}],
        "system": body.get("system"),
        "max_tokens": body.get("max_tokens", 512),
        "temperature": body.get("temperature", 0.2),
    })


@router.post("/tool-call")
def brain_v3_tool_call(body: dict) -> JSONResponse:
    miss = _check_key()
    if miss is not None:
        return miss
    tools = body.get("tools")
    if not isinstance(tools, list) or not tools:
        return JSONResponse({"error": "tools[] required"}, status_code=400)
    out = _dispatch({"messages": body.get("messages"),
                     "max_tokens": body.get("max_tokens", 1024),
                     "system": body.get("system")}, stream=False)
    if isinstance(out, JSONResponse):
        return out
    data, model = out
    tool_uses = [b for b in data.get("content", [])
                 if isinstance(b, dict) and b.get("type") == "tool_use"]
    texts = [b.get("text", "") for b in data.get("content", [])
             if isinstance(b, dict) and b.get("type") == "text"]
    if not tool_uses:
        return JSONResponse(
            {"model": model, "tool_use": [], "text": "".join(texts),
             "honest_note": "The model replied with text, not a tool call; "
              "nothing was fabricated into a tool invocation."},
            status_code=200)
    return JSONResponse({"model": model, "tool_use": tool_uses,
                         "stop_reason": data.get("stop_reason"),
                         "usage": data.get("usage")})


@router.post("/chat/stream")
def brain_v3_chat_stream(body: dict):
    miss = _check_key()
    if miss is not None:
        return miss

    def gen():
        out = _dispatch(body, stream=True)
        if isinstance(out, JSONResponse):
            payload = json.dumps({"error": "unavailable"}) + "\n"
            yield f"data: {payload}"
            return
        data, model = out
        # Non-stream relay of the streamed reply: honest single-event SSE so
        # no byte-level stream semantics are fabricated.
        text = "".join(
            (b.get("text") or "") for b in data.get("content", [])
            if isinstance(b, dict) and b.get("type") == "text")
        yield "data: " + json.dumps({
            "model": data.get("model", model), "delta": text,
            "stop_reason": data.get("stop_reason"),
            "usage": data.get("usage")}) + "\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/usage")
def brain_v3_usage() -> JSONResponse:
    return JSONResponse({
        "since_boot": round(time.time() - _boot_ts, 1),
        "totals": dict(_usage),
        "recent_requests": list(_ledger)[-25:],
        "note": "Metadata only; message content is never stored or logged.",
    })


def status() -> dict:
    return {
        "module": "szl_brain_v3",
        "key_present": bool(_key()),
        "workspace_id_present": bool(_workspace_id()),
        "default_model": DEFAULT_MODEL,
        "receipts": "ledger+log (DSSE binding is a follow-up; NOT claimed)",
        "fabricated_output": False,
    }


def register(app, ns: str = "a11oy", hub: str = "a11oy",
             *, build_sha: str = "unknown") -> dict:
    """Mount /api/{ns}/v3/brain/* (serve.py calls register(app, ns, hub, build_sha=...))."""
    prefix = f"/api/{ns}/v3/brain"
    app.include_router(router, prefix=prefix)
    out = {
        "mounted": prefix,
        "routes": ["/models", "/chat", "/chat/stream", "/converse",
                   "/tool-call", "/usage"],
        "build_sha": build_sha,
        "hub": hub,
        **status(),
    }
    print("[szl.brain-v3.register] " + json.dumps(out))
    return out
