# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
szl_prod_hardening.py — production-grade HTTP hardening for the a11oy API.

ONE additive module, wired onto an existing FastAPI ``app`` via
``register(app, ns="a11oy")``. It NEVER replaces an existing route, NEVER edits
another module, and — critically — every hardening feature is wrapped so that a
failure inside it can never take the app down: the middleware FAIL OPEN (on any
internal error the request/response passes through untouched). This matches the
per-organ ``register(app, ns=...)`` discipline already used across the fleet
(see szl_dark_surfaces_register.py, szl_be_hardening.py).

WHY (top-tech production hardening — each individually safe, additive, honest):

  1. SECURITY HEADERS on every response (OWASP Secure Headers Project / OWASP
     REST Security Cheat Sheet). For a JSON API the high-value, zero-breakage set is:
       X-Content-Type-Options: nosniff      — kill MIME sniffing.
       Referrer-Policy: no-referrer          — never leak the API URL/query.
       Content-Security-Policy: default-src 'none';
                                frame-ancestors 'self' https://huggingface.co
                                  https://*.hf.space https://*.huggingface.co;
                                base-uri 'none'; form-action 'none'
                                             — a JSON API renders nothing, so the
                                               strictest CSP is correct; the one
                                               relaxation is a frame-ancestors
                                               allow-list so Hugging Face can
                                               embed the Space (2026-06-17 iframe
                                               fix). We do NOT send the legacy
                                               X-Frame-Options header: it cannot
                                               express an allow-list and DENY here
                                               refused the legitimate HF embed.
       Strict-Transport-Security: max-age=63072000; includeSubDomains
                                             — pin HTTPS for browser clients.
     We do NOT clobber a Content-Security-Policy already set by an upstream
     HTML route (the SPA / docs pages may need a looser policy) — headers are
     only added when absent, so existing HTML surfaces keep their own CSP.

  2. RATE LIMITING — a lightweight in-memory token-bucket per client IP
     (default 300 req / 60 s / IP, fully configurable via env). Over the limit
     returns HTTP 429 with a ``Retry-After`` header (seconds), per the OWASP /
     industry norm of honoring Retry-After. Liveness probes (/healthz, /readyz,
     /livez, /health, /ping) are EXEMPT so orchestrators never get throttled, and
     the human-facing HTML page/static routes are EXEMPT too (DEMO-FLOOR FIX) so
     rapid tab-clicking from one booth IP never serves a raw rate_limited body in
     place of a page. Only the JSON DATA surface (/api/*, /feeds/*) is metered, so
     real abuse is still capped. Pure stdlib (no slowapi / redis); fixed-memory
     (bounded LRU of buckets).

  3. REQUEST ID + STRUCTURED ACCESS LOG — every response carries an
     ``X-Request-ID`` (uuid4, or the inbound one if a trusted client supplied it),
     and one structured JSON line is emitted per request with
     {method, path, status, latency_ms, request_id, ip}. NO bodies, NO query
     string, NO headers, NO secrets are logged. Observability baseline.

  4. RESPONSE CACHING — for read-only GETs the middleware adds conservative
     ``Cache-Control`` + a strong ``ETag`` (computed only for small bodies) and
     answers conditional requests (If-None-Match -> 304). A tiny bounded TTL
     micro-cache short-circuits repeated identical GETs. This is the HTTP layer
     ONLY; it coordinates conceptually with the backend-hardening PR that caches
     fabric probes server-side. Mutating verbs and already-cache-controlled
     responses are never touched.

  5. GRACEFUL ERROR ENVELOPE — an exception handler returns a consistent JSON
     shape ``{"error", "path", "request_id", "ts"}`` for unhandled exceptions.
     No stack trace, no internal repr, no message detail is leaked to clients
     (the real exception is logged server-side only). HONEST: the status code is
     a true 5xx (or the real HTTPException code) — NEVER a fake 200.

CONFIG (all optional, env-driven; safe defaults):
  A11OY_RL_LIMIT          requests per window per IP   (default 300)
  A11OY_RL_WINDOW_S       window seconds               (default 60)
  A11OY_HARDEN_HSTS       "0" disables HSTS header     (default on)
  A11OY_HARDEN_RATELIMIT  "0" disables rate limiting   (default on)
  A11OY_HARDEN_CACHE      "0" disables cache/ETag layer (default on)

DOCTRINE v11 LOCKED 749/14/163. Λ = Conjecture 1 (NEVER a theorem, never
"proven trust"). Organs EXPERIMENTAL. joules SAMPLE until on-box NVML; NO
free-energy claims. sovereign:true only on own metal. locked = 8. NO key
committed. NO fake 200. NO secret logged.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION
# Purpose:       Production HTTP hardening for the a11oy FastAPI app. One call:
#                register(app, ns="a11oy") wires everything additively + fail-open.
# Key entry pts: register(app, ns) -> list[str] status lines
#                ProdHardeningMiddleware (BaseHTTPMiddleware) — headers, rate
#                limit, request-id, access log, cache/ETag in one pass.
# What it adds:  OWASP security headers, per-IP token-bucket 429+Retry-After,
#                X-Request-ID + structured JSON access log, Cache-Control/ETag
#                /304 for read-only GETs, uniform {error,path,request_id,ts}
#                envelope for unhandled exceptions (true 5xx, never fake 200).
# Doctrine note: EVERY feature fail-open — an internal error never breaks the
#                request. Liveness probes exempt from rate limit. Stdlib only.
# ---------------------------------------------------------------------------
from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

# Single source of truth for the joules honesty label. This hardening layer has NO
# on-box NVML exporter, so the helper resolves to "sample" — the doctrine echo below
# uses it so the joules posture is decided in ONE place, never a stray literal.
# Wrapped so a missing/broken import can never take down the hardening surface.
try:
    from szl_joules_truth import joules_label as _joules_truth_label
except Exception:  # pragma: no cover - defensive: doctrine default is always sample
    def _joules_truth_label(_exporter_sample, now=None):  # type: ignore
        return "sample"

# ---------------------------------------------------------------------------
# Doctrine echo block — same shape the other szl_* surfaces emit, so any
# response reusing this constant stays honesty-clean under the doctrine guards.
# ---------------------------------------------------------------------------
DOCTRINE = {
    "version": "v11",
    "counts": "749/14/163",
    "locked": 8,
    "lambda": "Conjecture 1",          # OPEN — never a theorem, never "proven trust"
    "organs": "EXPERIMENTAL",
    "joules": "SAMPLE until on-box NVML",
    # joules_label decided by the single source of truth (no on-box exporter here
    # -> "sample"); never a hardcoded "measured" literal.
    "joules_label": _joules_truth_label(None),
    "free_energy": False,
    "sovereign": "only on own metal",
    "key_committed": False,
}

# Liveness / readiness probe paths — EXEMPT from rate limiting so an
# orchestrator's health checks are never throttled (a throttled liveness probe
# would get the pod killed — the opposite of hardening).
_LIVENESS_PATHS = frozenset(
    {"/healthz", "/readyz", "/livez", "/health", "/ping", "/_health", "/_ping"}
)

# DEMO-FLOOR FIX (2026-06-17): the human-facing HTML page/static routes are EXEMPT
# from the per-IP limiter so a booth clicking rapidly through tabs on ONE shared IP
# never gets a raw rate_limited body in place of a page. Only the JSON DATA surface
# (/api/*, /feeds/*, /osint/*) is metered, so real abuse is still capped. These
# mirror the demo page routes in serve.py.
_PAGE_EXEMPT_EXACT = frozenset({
    "/", "/console", "/frontier", "/energy-ops", "/energy", "/holographic",
    "/energy-holographic", "/energy-sovereign", "/governance",
    "/signature-is-not-proof", "/defense-readiness", "/pinn", "/pnt", "/fabric",
    "/harvest", "/elite", "/estate-hologram", "/doctrine", "/platform",
    "/warhacker", "/proven-formulas", "/company", "/restraint", "/waqay", "/yupay",
    "/operator", "/cathedral", "/live-wires", "/orbital",
    "/honest", "/favicon.ico", "/robots.txt",
})
_PAGE_EXEMPT_PREFIXES = (
    "/elite", "/mbse", "/static", "/assets", "/cesium",
    "/web/", "/pages/", "/static-vendor", "/.well-known",
)


def _is_rate_limited_path(path: str) -> bool:
    """True only for the JSON DATA surface that should be metered. Liveness probes
    and human-facing page/static routes are EXEMPT so the showcase always renders;
    only /api/*, /feeds/*, /osint/* (where real abuse lands) are metered."""
    p = (path or "/").rstrip("/") or "/"
    if p in _LIVENESS_PATHS or p in _PAGE_EXEMPT_EXACT:
        return False
    for pre in _PAGE_EXEMPT_PREFIXES:
        if p == pre or p.startswith(pre + "/"):
            return False
    if "/api/" in p or p.startswith("/feeds") or p.startswith("/osint"):
        return True
    # Default: do NOT rate-limit unknown/page-like routes (fail-open for the demo).
    return False


def _env_flag(name: str, default: bool = True) -> bool:
    """Read a boolean env flag; only the literal "0"/"false"/"no" disable it."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int) -> int:
    try:
        v = int(os.environ.get(name, "").strip())
        return v if v > 0 else default
    except Exception:
        return default


def _stderr(msg: str) -> None:
    try:
        print(msg, file=sys.stderr)
    except Exception:
        pass


# ===========================================================================
# Token-bucket rate limiter (pure stdlib, fixed memory, thread-safe).
# ===========================================================================
class _TokenBucketLimiter:
    """Per-key token bucket. ``limit`` tokens refilled over ``window`` seconds.

    Memory is bounded: at most ``max_keys`` buckets are retained (LRU eviction),
    so a flood of distinct source IPs cannot exhaust memory. Thread-safe.
    """

    def __init__(self, limit: int, window: float, max_keys: int = 4096) -> None:
        self.limit = float(max(1, limit))
        self.window = float(max(1.0, window))
        self.refill_per_s = self.limit / self.window
        self.max_keys = max_keys
        self._buckets: "OrderedDict[str, Tuple[float, float]]" = OrderedDict()
        self._lock = threading.Lock()

    def check(self, key: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """Consume one token for ``key``.

        Returns (allowed, retry_after_seconds). retry_after is 0 when allowed.
        """
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._buckets.get(key, (self.limit, now))
            # Refill based on elapsed time, capped at limit.
            tokens = min(self.limit, tokens + (now - last) * self.refill_per_s)
            if tokens >= 1.0:
                tokens -= 1.0
                allowed, retry_after = True, 0
            else:
                allowed = False
                # Seconds until one whole token is available again.
                needed = 1.0 - tokens
                retry_after = max(1, int(needed / self.refill_per_s + 0.999))
            self._buckets[key] = (tokens, now)
            self._buckets.move_to_end(key)
            # Bound memory: evict the least-recently-used bucket.
            while len(self._buckets) > self.max_keys:
                self._buckets.popitem(last=False)
            return allowed, retry_after


# ===========================================================================
# Tiny bounded TTL micro-cache for idempotent GET responses (HTTP layer).
# ===========================================================================
class _TTLCache:
    def __init__(self, ttl: float = 2.0, max_items: int = 512) -> None:
        self.ttl = ttl
        self.max_items = max_items
        self._d: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            item = self._d.get(key)
            if not item:
                return None
            ts, val = item
            if now - ts > self.ttl:
                self._d.pop(key, None)
                return None
            self._d.move_to_end(key)
            return val

    def put(self, key: str, val: Any) -> None:
        with self._lock:
            self._d[key] = (time.monotonic(), val)
            self._d.move_to_end(key)
            while len(self._d) > self.max_items:
                self._d.popitem(last=False)


def _client_ip(request: Any) -> str:
    """Best-effort client IP. Honors X-Forwarded-For first hop if present."""
    try:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip() or "unknown"
        client = getattr(request, "client", None)
        if client and getattr(client, "host", None):
            return client.host
    except Exception:
        pass
    return "unknown"


def _safe_etag(body: bytes) -> str:
    """Strong ETag = quoted sha256 hex of the body (cheap, only for small bodies)."""
    return '"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def build_middleware(ns: str = "a11oy"):
    """Construct the ProdHardeningMiddleware class bound to runtime config.

    Returns the middleware class (so callers can ``app.add_middleware(...)``).
    Imports starlette lazily so importing this module never hard-requires it.
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse, Response

    rl_enabled = _env_flag("A11OY_HARDEN_RATELIMIT", True)
    hsts_enabled = _env_flag("A11OY_HARDEN_HSTS", True)
    cache_enabled = _env_flag("A11OY_HARDEN_CACHE", True)
    rl_limit = _env_int("A11OY_RL_LIMIT", 300)
    rl_window = _env_int("A11OY_RL_WINDOW_S", 60)

    limiter = _TokenBucketLimiter(rl_limit, rl_window) if rl_enabled else None
    micro_cache = _TTLCache() if cache_enabled else None

    # JSON-API-appropriate CSP: the response renders nothing, so deny everything
    # EXCEPT framing, where we use a frame-ancestors allow-list instead of a blanket
    # 'none'. 2026-06-17 iframe fix: `frame-ancestors 'none'` (and the legacy
    # X-Frame-Options: DENY) REFUSED the legitimate Hugging Face cross-origin embed
    # (huggingface.co framing szlholdings-*.hf.space) — the founder's actual view —
    # so the Space rendered a white screen + red 🚫. We scope frame-ancestors to
    # self + Hugging Face: clickjacking protection is retained (no other origin may
    # frame us) while HF can embed. The rest of the CSP stays maximally strict.
    CSP = (
        "default-src 'none'; "
        "frame-ancestors 'self' https://huggingface.co "
        "https://*.hf.space https://*.huggingface.co; "
        "base-uri 'none'; form-action 'none'"
    )
    HSTS = "max-age=63072000; includeSubDomains"

    # NOTE: we intentionally do NOT emit the legacy `X-Frame-Options` header.
    # X-Frame-Options can only say SAMEORIGIN/DENY and cannot express the HF
    # allow-list above; modern browsers honor CSP frame-ancestors instead. Keeping
    # X-Frame-Options: DENY here is exactly what blocked the HF embed.
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
    }

    def _apply_security_headers(resp: "Response") -> None:
        """Add headers only when absent so HTML/SPA routes keep their own policy."""
        try:
            for k, v in SECURITY_HEADERS.items():
                if k not in resp.headers:
                    resp.headers[k] = v
            # Only set a strict CSP if the route did not already declare one
            # (the SPA / docs may need a looser policy for inline scripts).
            if "Content-Security-Policy" not in resp.headers:
                resp.headers["Content-Security-Policy"] = CSP
            if hsts_enabled and "Strict-Transport-Security" not in resp.headers:
                resp.headers["Strict-Transport-Security"] = HSTS
        except Exception:  # fail-open: never let header logic break a response
            pass

    class ProdHardeningMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            start = time.monotonic()
            # --- request id (honor a sane inbound one, else mint a uuid4) -----
            try:
                inbound = request.headers.get("x-request-id", "")
                req_id = inbound if (inbound and len(inbound) <= 200) else uuid.uuid4().hex
            except Exception:
                req_id = uuid.uuid4().hex
            try:
                request.state.request_id = req_id
            except Exception:
                pass

            path = getattr(getattr(request, "url", None), "path", "") or ""
            method = getattr(request, "method", "GET")
            ip = _client_ip(request)
            is_liveness = path in _LIVENESS_PATHS
            # DEMO-FLOOR FIX: only meter the JSON data surface; liveness probes and
            # human-facing page/static routes are exempt so the showcase always renders.
            is_metered = _is_rate_limited_path(path)

            # --- rate limit (fail-open; pages + liveness exempt) --------------
            if limiter is not None and is_metered:
                try:
                    allowed, retry_after = limiter.check(ip)
                except Exception:
                    allowed, retry_after = True, 0  # fail-open
                if not allowed:
                    resp = JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "path": path,
                            "request_id": req_id,
                            "ts": time.time(),
                        },
                    )
                    resp.headers["Retry-After"] = str(retry_after)
                    resp.headers["X-Request-ID"] = req_id
                    _apply_security_headers(resp)
                    _access_log(method, path, 429, start, req_id, ip)
                    return resp

            # --- micro-cache lookup for idempotent GET ------------------------
            cache_key = None
            if micro_cache is not None and method == "GET":
                try:
                    qs = getattr(getattr(request, "url", None), "query", "") or ""
                    cache_key = f"{path}?{qs}"
                    cached = micro_cache.get(cache_key)
                    if cached is not None:
                        c_body, c_status, c_ctype, c_etag = cached
                        inm = request.headers.get("if-none-match", "")
                        if c_etag and inm and c_etag in inm:
                            resp = Response(status_code=304)
                            resp.headers["ETag"] = c_etag
                        else:
                            resp = Response(content=c_body, status_code=c_status, media_type=c_ctype)
                            if c_etag:
                                resp.headers["ETag"] = c_etag
                            resp.headers["Cache-Control"] = "public, max-age=2"
                        resp.headers["X-Request-ID"] = req_id
                        resp.headers["X-Cache"] = "HIT"
                        _apply_security_headers(resp)
                        _access_log(method, path, resp.status_code, start, req_id, ip)
                        return resp
                except Exception:
                    cache_key = None  # fail-open

            # --- run the downstream app ---------------------------------------
            try:
                response = await call_next(request)
            except Exception as exc:
                # GRACEFUL ERROR ENVELOPE — honest 500, no stack trace leaked.
                _stderr(json.dumps({
                    "lvl": "error", "ns": ns, "request_id": req_id,
                    "method": method, "path": path,
                    "exc_type": type(exc).__name__,  # type only, no message/secret
                }))
                resp = JSONResponse(
                    status_code=500,
                    content={
                        "error": "internal_error",
                        "path": path,
                        "request_id": req_id,
                        "ts": time.time(),
                    },
                )
                resp.headers["X-Request-ID"] = req_id
                _apply_security_headers(resp)
                _access_log(method, path, 500, start, req_id, ip)
                return resp

            # --- success path: headers, request-id, cache, log ----------------
            try:
                response.headers["X-Request-ID"] = req_id
            except Exception:
                pass
            _apply_security_headers(response)

            # Cache/ETag for small, OK, read-only GET JSON responses only.
            if (
                micro_cache is not None
                and method == "GET"
                and getattr(response, "status_code", 200) == 200
                and "Cache-Control" not in response.headers
                and not is_liveness
            ):
                try:
                    body = await _read_body(response)
                    if body is not None and len(body) <= 64 * 1024:
                        etag = _safe_etag(body)
                        ctype = response.headers.get("content-type", "application/json")
                        inm = request.headers.get("if-none-match", "")
                        if cache_key:
                            micro_cache.put(cache_key, (body, 200, ctype, etag))
                        if inm and etag in inm:
                            new_resp = Response(status_code=304)
                            new_resp.headers["ETag"] = etag
                        else:
                            new_resp = Response(content=body, status_code=200, media_type=ctype)
                            new_resp.headers["ETag"] = etag
                            new_resp.headers["Cache-Control"] = "public, max-age=2"
                        new_resp.headers["X-Request-ID"] = req_id
                        new_resp.headers["X-Cache"] = "MISS"
                        _apply_security_headers(new_resp)
                        _access_log(method, path, new_resp.status_code, start, req_id, ip)
                        return new_resp
                except Exception:
                    pass  # fail-open: return the original response untouched

            _access_log(method, path, getattr(response, "status_code", 0), start, req_id, ip)
            return response

    return ProdHardeningMiddleware


async def _read_body(response) -> Optional[bytes]:
    """Drain a streaming response body into bytes (fail-open -> None)."""
    try:
        if hasattr(response, "body") and isinstance(getattr(response, "body"), (bytes, bytearray)):
            return bytes(response.body)
        chunks = []
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            chunks.append(chunk if isinstance(chunk, (bytes, bytearray)) else str(chunk).encode())
        return b"".join(chunks)
    except Exception:
        return None


def _access_log(method: str, path: str, status: int, start: float, req_id: str, ip: str) -> None:
    """One structured JSON access line. NO bodies, NO query, NO secrets."""
    try:
        latency_ms = round((time.monotonic() - start) * 1000.0, 2)
        _stderr(json.dumps({
            "lvl": "info", "kind": "access",
            "method": method, "path": path, "status": status,
            "latency_ms": latency_ms, "request_id": req_id, "ip": ip,
        }))
    except Exception:
        pass


def register(app: Any, ns: str = "a11oy") -> List[str]:
    """Wire production HTTP hardening onto ``app`` (ADDITIVE, FAIL-OPEN).

    Adds ONE middleware (security headers + rate limit + request-id + access
    log + cache/ETag) and ONE catch-all exception handler (graceful error
    envelope). Returns human-readable status lines. The whole thing is guarded:
    if hardening cannot be wired, the app is returned untouched and we say so.
    """
    status: List[str] = []

    # --- the all-in-one middleware ----------------------------------------
    try:
        mw = build_middleware(ns=ns)
        app.add_middleware(mw)
        line = (f"[a11oy:prod-harden] middleware wired: security-headers + "
                f"rate-limit({_env_int('A11OY_RL_LIMIT',300)}/{_env_int('A11OY_RL_WINDOW_S',60)}s/IP data-surface, pages exempt, "
                f"429+Retry-After) + request-id + access-log + cache/ETag")
        _stderr(line)
        status.append(line)
    except Exception as exc:  # additive: a wiring failure never breaks the app
        line = f"[a11oy:prod-harden] middleware NOT wired (app unchanged): {exc!r}"
        _stderr(line)
        status.append(line)

    # --- graceful error envelope (catch-all 500 handler) ------------------
    try:
        from starlette.responses import JSONResponse

        async def _envelope_handler(request, exc):  # honest 500, no stack leak
            try:
                req_id = getattr(getattr(request, "state", None), "request_id", "") or uuid.uuid4().hex
                path = getattr(getattr(request, "url", None), "path", "") or ""
            except Exception:
                req_id, path = uuid.uuid4().hex, ""
            _stderr(json.dumps({
                "lvl": "error", "ns": ns, "kind": "unhandled",
                "request_id": req_id, "path": path,
                "exc_type": type(exc).__name__,  # type only — never the message
            }))
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "path": path,
                    "request_id": req_id,
                    "ts": time.time(),
                },
                headers={"X-Request-ID": req_id},
            )

        # Register for the generic Exception class (true 5xx — never a fake 200).
        add_handler = getattr(app, "add_exception_handler", None)
        if callable(add_handler):
            app.add_exception_handler(Exception, _envelope_handler)
            line = "[a11oy:prod-harden] error envelope wired: {error,path,request_id,ts} (honest 500, no stack leak)"
        else:
            line = "[a11oy:prod-harden] error envelope NOT wired (app lacks add_exception_handler)"
        _stderr(line)
        status.append(line)
    except Exception as exc:
        line = f"[a11oy:prod-harden] error envelope NOT wired: {exc!r}"
        _stderr(line)
        status.append(line)

    return status
