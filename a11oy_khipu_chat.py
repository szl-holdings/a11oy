#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Same-origin Khipu CPU-lab proxy so an investor can Try Khipu from /console.

The browser on a-11-oy.com cannot rely on CORS to the lab Space. This module
proxies:

  GET  /api/a11oy/v1/khipu/status  — lab /healthz + pin (no signing)
  POST /api/a11oy/v1/khipu/chat    — /v1/chat/completions (max_tokens<=32,
                                     temperature=0, stream=false)

Auth is the publicly documented dummy Bearer not-a-secret. HF_TOKEN is never
read or forwarded. GET does not mint a receipt. POST passes through the lab's
UNSIGNED record_sha256 when present; missing fields are UNKNOWN.

GPU Inference Endpoint remains ROADMAP. Forge lab is SNAPSHOT.
killinchu detector stays SIMULATED. Λ = Conjecture 1.
"""
import hashlib
import sys
import time
from pathlib import Path

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from packages.inference.src.voters.khipu_gguf import (
    KHIPU_LAB_DUMMY_BEARER,
    KHIPU_MAX_TOKENS,
    KHIPU_MEASURED_PROBE_2026_08_28,
    KHIPU_TEMPERATURE,
    clamp_max_tokens,
    extract_lab_receipt,
    khipu_lab_base,
    khipu_pin,
)

_STATUS_PATH = "/api/a11oy/v1/khipu/status"
_CHAT_PATH = "/api/a11oy/v1/khipu/chat"
_PROMPT_CHAR_CAP = 4000


def _honesty() -> dict:
    return {
        "lab": "MEASURED this request when /healthz returns READY; else FAILED",
        "gpu_inference_endpoint": "ROADMAP",
        "forge_lab": "SNAPSHOT",
        "killinchu_detector": "SIMULATED",
        "lambda": "Conjecture 1",
        "tokens_per_second": "not reported",
        "signing": "UNSIGNED unless the lab returns a signature; never fabricated",
    }


def _headers() -> dict:
    return {
        "Authorization": "Bearer %s" % KHIPU_LAB_DUMMY_BEARER,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _healthz() -> tuple[str, dict | None, str | None]:
    url = khipu_lab_base() + "/healthz"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
        if not isinstance(body, dict):
            body = {"raw_status": resp.status_code}
        status = str(body.get("status") or "").upper()
        if resp.status_code == 200 and status == "READY":
            return "READY", body, None
        return "FAILED", body, "healthz HTTP %s status=%s" % (resp.status_code, status or "UNKNOWN")
    except Exception as exc:
        return "FAILED", None, "%s: %s" % (type(exc).__name__, exc)


async def _handle_status(request: Request) -> JSONResponse:
    lab_status, healthz, err = await _healthz()
    payload = {
        "lab_status": lab_status,
        "healthz": healthz,
        "error": err,
        "pin": khipu_pin(),
        "honesty": _honesty(),
        "measured_probe_2026_08_28": KHIPU_MEASURED_PROBE_2026_08_28,
        "doctrine": {
            "version": "v11",
            "locked_formulas": 8,
            "lambda": "Conjecture 1",
        },
    }
    return JSONResponse(payload)


async def _handle_chat(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception as exc:
        return JSONResponse({"ok": False, "lab_status": "FAILED", "error": "invalid JSON: %s" % exc}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "lab_status": "FAILED", "error": "JSON object required"}, status_code=400)

    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"ok": False, "lab_status": "FAILED", "error": "prompt required"}, status_code=422)
    if len(prompt) > _PROMPT_CHAR_CAP:
        prompt = prompt[:_PROMPT_CHAR_CAP]

    max_tokens = clamp_max_tokens(body.get("max_tokens", KHIPU_MAX_TOKENS))
    system = body.get("system")
    messages = []
    if isinstance(system, str) and system.strip():
        messages.append({"role": "system", "content": system.strip()[:1000]})
    messages.append({"role": "user", "content": prompt})

    pin = khipu_pin()
    payload = {
        "model": "%s@%s" % (pin["model_repo"], pin["model_rev"]),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": KHIPU_TEMPERATURE,
        "stream": False,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                khipu_lab_base() + "/v1/chat/completions",
                json=payload,
                headers=_headers(),
            )
        wall_ms = round((time.monotonic() - t0) * 1000, 1)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        extracted = extract_lab_receipt(data)
        ok = resp.status_code == 200 and bool(extracted["text"])
        lab_status = "READY" if ok else "FAILED"
        # Prefer the lab's elapsed_ms when present; otherwise this proxy's wall.
        elapsed = extracted["elapsed_ms"] if extracted["elapsed_ms"] is not None else wall_ms
        out = {
            "ok": ok,
            "lab_status": lab_status,
            "http_status": resp.status_code,
            "text": extracted["text"] if ok else None,
            "signature": extracted["signature"] if ok else "UNKNOWN",
            "record_sha256": extracted["record_sha256"] if ok else "UNKNOWN",
            "usage": extracted["usage"] if ok else {},
            "usage_label": "REPORTED" if (ok and extracted["usage"]) else "UNKNOWN",
            "elapsed_ms": elapsed,
            "elapsed_ms_label": "MEASURED",
            "wall_ms": wall_ms,
            "model": extracted["model"],
            "pin": pin,
            "honesty": _honesty(),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "error": None if ok else (data.get("error") or ("lab HTTP %s" % resp.status_code)),
        }
        status_code = 200 if ok else (resp.status_code if resp.status_code >= 400 else 502)
        return JSONResponse(out, status_code=status_code)
    except Exception as exc:
        wall_ms = round((time.monotonic() - t0) * 1000, 1)
        return JSONResponse(
            {
                "ok": False,
                "lab_status": "FAILED",
                "text": None,
                "signature": "UNKNOWN",
                "record_sha256": "UNKNOWN",
                "usage": {},
                "usage_label": "UNKNOWN",
                "elapsed_ms": wall_ms,
                "elapsed_ms_label": "MEASURED",
                "pin": pin,
                "honesty": _honesty(),
                "error": "%s: %s" % (type(exc).__name__, exc),
            },
            status_code=502,
        )


def register(app) -> str:
    """Mount + front-move so exact paths beat /api/a11oy/{path:path} and the SPA."""
    app.add_api_route(_STATUS_PATH, _handle_status, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route(_CHAT_PATH, _handle_chat, methods=["POST"], include_in_schema=False)
    for target in (_STATUS_PATH, _CHAT_PATH):
        for index, route in enumerate(app.router.routes):
            if getattr(route, "path", None) == target:
                app.router.routes.insert(0, app.router.routes.pop(index))
                break
    return (
        "%s + %s (CPU lab proxy; dummy auth; max_tokens<=32; temperature=0; "
        "no stream; no tokens/s; Λ=Conjecture 1)"
        % (_STATUS_PATH, _CHAT_PATH)
    )


if __name__ == "__main__":
    from fastapi import FastAPI, Request
    from starlette.testclient import TestClient

    app = FastAPI()

    async def _ok_status(request: Request):
        return JSONResponse({"lab_status": "READY"})

    app.add_api_route(_STATUS_PATH, _ok_status, methods=["GET"])
    st = register(app)
    assert _STATUS_PATH in st and _CHAT_PATH in st
    c = TestClient(app)
    r = c.get(_STATUS_PATH)
    assert r.status_code == 200
    print("a11oy_khipu_chat: ALL OK — %s" % st)
