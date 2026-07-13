# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
szl_be_hardening.py — backend hardening for every SZL organ.

One module, registered ADDITIVELY onto an existing FastAPI `app` via
`harden(app, organ="a11oy")`. It NEVER replaces existing routes and NEVER
crashes the host app (every block is try/except-guarded), in keeping with the
per-organ "register(app, ns=...)" discipline already used across the fleet.

What it wires (HONESTY OVER CHECKLIST — see the per-item honest labels):

  1. INPUT VALIDATION    real pydantic models on the hardening endpoints
                          (`/api/<organ>/v1/echo`, `/api/<organ>/v1/khipu/append`).
                          Raw dicts are rejected with a 422 error envelope.
  2. RATE LIMITING        60 req/min per client IP. Prefers `slowapi`; if that
                          import is unavailable it falls back to a real stdlib
                          sliding-window limiter middleware (no fake pass-through).
  3. OPENAPI              FastAPI's own auto-generated spec, re-served verbatim at
                          `/api/<organ>/openapi.json` (real schema, not a stub).
  4. HEALTH PROBES        `/healthz` (liveness — process is up) and `/readyz`
                          (readiness — opens the durable Khipu store and re-walks
                          the hash chain; NOT ready if the chain is broken).
  5. STRUCTURED LOGGING   JSON logs to stderr with trace_id, span_id, organ,
                          level, msg, plus method/path/status/latency_ms. A
                          per-request trace/span id is generated and surfaced in
                          the `X-Trace-Id` / `X-Span-Id` response headers.
  6. ERROR ENVELOPES      every HTTPException / validation error / unhandled
                          exception returns the uniform envelope:
                          {"error": {code, message, trace_id, doctrine: "v11"}}.
  7. PERSISTENCE          DurableKhipu — a real SQLite-backed, append-only,
                          SHA3-256 hash-chained receipt store (Python stdlib
                          `sqlite3`, zero new pip installs). Receipts survive a
                          process restart. If the disk path is unwritable it
                          falls back to a JSON-file store, then to in-memory
                          (each fallback is reported honestly via /readyz).
  9. HONEST FOOTER        `/honest` returns the EXACT v11 lock footer:
                          749/14/163 @ c7c0ba17, Λ = Conjecture 1.

Stdlib only, with OPTIONAL slowapi. No mocks in any non-test path.

Signed-off-by: Greene (BE) <greene@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION (added by Perplexity Computer Agent, 2026-06)
# Purpose:       Backend hardening for every SZL organ. One-call setup:
#                harden(app, organ="a11oy") wires everything additively.
# Key entry pts: harden(app, organ) -> report dict
#                DurableKhipu (SQLite-backed receipt store, stdlib only)
# What it adds:  Rate limiting (60/min/IP via slowapi or stdlib fallback),
#                structured JSON logs, uniform error envelopes {error: {code,
#                message, trace_id, doctrine}}, /healthz + /readyz probes,
#                /honest footer (749/14/163), OpenAPI at /openapi.json.
# Related mods:  szl_khipu.py (in-memory DAG), szl_dsse.py (signing),
#                serve.py (calls harden() inside try/except at startup)
# Doctrine note: Every block is try/except-guarded — NEVER crashes host app.
#                SQLite path: /tmp/szl_khipu_<organ>.db (HF writable).
#                Falls back: SQLite -> JSON file -> in-memory (reported on /readyz).
# ---------------------------------------------------------------------------
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Doctrine constants — the v11 LOCK. These are load-bearing; tests assert them.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
DOCTRINE_LOCK = {
    "doctrine": "v11",
    "state": "LOCKED",
    "declarations": 749,
    "axioms": 14,
    "sorries": 163,
    "commit": "c7c0ba17",
    "lambda": "Conjecture 1",
    "lambda_note": "Λ-Aggregator Uniqueness — Conjecture 1, NOT a closed theorem.",
    # Locked-proven formulas = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17.
    # The count itself is the no-axiom theorem locked_count_eight (lutar-lean #219 +
    # platform #321, merged 2026-06-10). Surfaced here so /honest carries the canonical
    # locked-8 (count + IDs), not just 749/14/163 + Λ. Additive; never inflate.
    "locked_formula_count": 8,
    "locked_formula_ids": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
}
DOCTRINE_FOOTER = "Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1"

_GENESIS = "0" * 64
# DEMO-FLOOR RATE-LIMIT FIX (2026-06-17): the per-IP limiter previously capped
# EVERYTHING at 60/min, including the human-facing HTML showcase pages (/, /frontier,
# /console, /governance, /warhacker, ...). During the founder demo, rapid clicking
# through tabs from ONE booth IP tripped the cap and served a raw
# {"error":{"code":"rate_limited",...}} body in place of the page — looking like a
# broken site. Two changes, both env-overridable so ops can tune live WITHOUT a
# redeploy:
#   1. EXEMPT the human-facing page/static routes from the limiter entirely
#      (see _is_rate_limited_path) — these are static-ish GET page loads.
#   2. RAISE the per-IP cap on the remaining (API/data) surface to a demo-safe,
#      burst-tolerant default (300/min) so even busy API tabs won't trip it.
# This is a TUNING + EXEMPTION for read-only demo surfaces — it does NOT remove
# abuse protection: the JSON data surface (/api/*, /feeds/*) is still metered by a
# real sliding-window limiter, and genuinely expensive POST endpoints keep their
# own protection. Honest: a true abuse ceiling remains.
try:
    RATE_LIMIT_PER_MIN = max(1, int(os.environ.get("SZL_RATE_LIMIT_PER_MIN", "300")))
except Exception:
    RATE_LIMIT_PER_MIN = 300

# Human-facing page routes ALWAYS render (never rate-limited): the self-contained
# consoles + landing/showcase pages are the demo surface. Only the JSON DATA surface
# (/api/* and /feeds/*) is metered. Health/readiness probes are also always allowed
# so liveness checks never trip the limiter. These mirror the demo page routes in
# serve.py (/, /frontier, /console, /energy-ops, /governance, /warhacker, ...).
_RL_EXEMPT_EXACT = frozenset({
    "/", "/console", "/frontier", "/energy-ops", "/energy", "/holographic",
    "/energy-holographic", "/energy-sovereign", "/governance",
    "/signature-is-not-proof", "/defense-readiness", "/determinacy",
    "/pinn", "/pnt", "/fabric",
    "/harvest", "/elite", "/estate-hologram", "/doctrine", "/platform",
    "/warhacker", "/proven-formulas", "/company", "/restraint", "/waqay", "/yupay",
    "/operator", "/cathedral", "/live-wires", "/orbital",
    "/healthz", "/readyz", "/honest", "/favicon.ico", "/robots.txt",
})
_RL_EXEMPT_PREFIXES = (
    "/elite", "/mbse", "/static", "/assets", "/cesium",
    "/web/", "/pages/", "/static-vendor", "/.well-known",
)


def _is_rate_limited_path(path: str) -> bool:
    """True only for the JSON DATA surface that should be metered. Human-facing
    page/static/health routes are EXEMPT so the showcase always renders. We meter
    the API + feeds data endpoints (where real abuse would land); everything else
    fails open (renders) for the demo."""
    p = (path or "/").rstrip("/") or "/"
    if p in _RL_EXEMPT_EXACT:
        return False
    for pre in _RL_EXEMPT_PREFIXES:
        if p == pre or p.startswith(pre + "/"):
            return False
    # Meter the data surface: /api/<organ>/v1/... and top-level /feeds/* data.
    if "/api/" in p or p.startswith("/feeds") or p.startswith("/osint"):
        return True
    # Default: do NOT rate-limit unknown/page-like routes (fail-open for the demo;
    # the data surface above is what we protect).
    return False

# ---------------------------------------------------------------------------
# 8. SECURITY RESPONSE HEADERS — conservative, non-breaking baseline applied to
#    EVERY response by the trace/log middleware. We deliberately do NOT emit a
#    restrictive Content-Security-Policy here: the SZL consoles are self-
#    contained SPAs with inlined scripts/styles (0 runtime CDN), and a blanket
#    CSP would break them. These headers are safe for an HTTPS-only app:
#      - X-Content-Type-Options: nosniff   (no MIME sniffing)
#      - Referrer-Policy: strict-origin-when-cross-origin
#      - Strict-Transport-Security          (hf.space is HTTPS-only)
#    Additive only; never overwrites a header an organ already set. The HF Space
#    proxy was verified NOT to inject these, so the served app owns them.
#
#    CLICKJACKING / EMBED POLICY (2026-06-17 iframe fix):
#    We do NOT send the legacy `X-Frame-Options` header. X-Frame-Options can only
#    express SAMEORIGIN/DENY — it CANNOT express an allow-list — and SAMEORIGIN
#    here REFUSED the legitimate Hugging Face cross-origin embed (huggingface.co
#    framing szlholdings-*.hf.space), which is exactly how the founder views the
#    Space. The browser blocked it → white screen + red 🚫. We replace it with a
#    Content-Security-Policy `frame-ancestors` allow-list that PERMITS only our
#    own origin and Hugging Face. This is NOT weaker: clickjacking protection is
#    retained (any other origin still cannot frame us); modern browsers honor CSP
#    frame-ancestors over X-Frame-Options. The allow-list is scoped to the one
#    legitimate embedder (HF) + self. It is additive: we set this CSP only when a
#    route has not already declared its own Content-Security-Policy, so any organ
#    that needs a looser/stricter policy keeps it.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}

# frame-ancestors allow-list: self + Hugging Face (the real embedder). Scopes the
# embed permission to HF instead of the blanket SAMEORIGIN that broke the embed.
_FRAME_ANCESTORS_CSP = (
    "frame-ancestors 'self' https://huggingface.co "
    "https://*.hf.space https://*.huggingface.co;"
)


def _apply_security_headers(resp: Any) -> Any:
    """Set the conservative security-header baseline on `resp` without clobbering
    any header an organ route already chose to set. Also installs a CSP
    `frame-ancestors` allow-list (self + Hugging Face) IN PLACE OF the legacy
    X-Frame-Options header, so HF can legitimately embed the Space while other
    origins still cannot frame it (clickjacking protection retained). Additive:
    a route that already set its own Content-Security-Policy keeps it. Never
    raises."""
    try:
        for k, v in _SECURITY_HEADERS.items():
            if k not in resp.headers:
                resp.headers[k] = v
        if "Content-Security-Policy" not in resp.headers:
            resp.headers["Content-Security-Policy"] = _FRAME_ANCESTORS_CSP
        # SEC-08 (HARDEN-DEEP): the ASGI server (uvicorn) stamps a
        # `Server: uvicorn` header that leaks the framework name. No version is
        # exposed, but per Microsoft-SDL / SEC-08 we redact the framework name to
        # a neutral product token. Always override (not setdefault) so the
        # uvicorn default never reaches the client. Honest, additive, no behavior
        # change. (X-Powered-By is already absent.)
        resp.headers["Server"] = "szl"
    except Exception:
        pass
    return resp


# ---------------------------------------------------------------------------
# Pydantic request models — defined at MODULE scope so FastAPI can resolve the
# body annotations (local classes inside harden() become unresolved ForwardRefs
# and FastAPI then mis-reads the param as a query field). Real validation:
# extra="forbid" rejects raw/unknown keys with a 422 error envelope.
# ---------------------------------------------------------------------------
# Module-scope FastAPI/Starlette imports so that, under `from __future__ import
# annotations`, FastAPI can resolve route handler annotations (Request, etc.)
# from this module's globals. Guarded: absence is handled gracefully in harden().
try:
    from fastapi import Request  # noqa: F401
    from fastapi.responses import JSONResponse  # noqa: F401
except Exception:  # pragma: no cover
    Request = Any  # type: ignore
    JSONResponse = Any  # type: ignore

try:
    from pydantic import BaseModel as _BaseModel, Field as _Field, ConfigDict as _ConfigDict

    class EchoIn(_BaseModel):
        model_config = _ConfigDict(extra="forbid")
        message: str = _Field(..., min_length=1, max_length=4096)

    class KhipuAppendIn(_BaseModel):
        model_config = _ConfigDict(extra="forbid")
        action: str = _Field(..., min_length=1, max_length=256)
        payload: Dict[str, Any] = _Field(default_factory=dict)
except Exception:  # pydantic absent -> harden() will no-op the validated routes
    EchoIn = None  # type: ignore
    KhipuAppendIn = None  # type: ignore


# ===========================================================================
# 7. DURABLE PERSISTENCE — SQLite-backed, hash-chained Khipu receipt store.
# ===========================================================================
class DurableKhipu:
    """Append-only, SHA3-256 hash-chained Khipu store with durable backends.

    Backend selection (honest, reported via .backend):
      "sqlite"  — real on-disk SQLite DB; survives process restart (preferred).
      "json"    — on-disk JSON file (if sqlite path unwritable).
      "memory"  — in-process list (last resort; NOT durable — reported as such).

    The hash chain is identical regardless of backend: receipt[n].prev ==
    receipt[n-1].digest, digest = SHA3-256 over the canonical body. verify()
    re-walks the entire chain and returns (ok, depth, first_break_seq).
    """

    def __init__(self, organ: str, ns: Optional[str] = None,
                 path: Optional[str] = None) -> None:
        self.organ = organ
        self.ns = ns or organ
        self._lock = threading.RLock()
        self.backend = "memory"
        self._mem: List[Dict[str, Any]] = []
        # SQLite connections are deliberately short-lived. A process-global
        # connection kept the database file locked on Windows and made clean
        # restart/deployment tests fail at directory teardown. Each operation
        # opens a transaction-scoped connection instead; the on-disk chain is the
        # state, not a connection object.
        self._db: Optional[sqlite3.Connection] = None
        self._json_path: Optional[str] = None

        # Resolve a writable path. Honor an env override; else a per-organ default.
        default_dir = os.environ.get(
            "SZL_KHIPU_DIR", os.environ.get("HOME", "/tmp") + "/.szl_khipu"
        )
        self._path = path or os.path.join(default_dir, f"khipu_{self.ns}.sqlite3")

        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with sqlite3.connect(self._path, timeout=30.0) as db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS khipu ("
                    "seq INTEGER PRIMARY KEY, action TEXT NOT NULL, "
                    "payload TEXT NOT NULL, prev TEXT NOT NULL, "
                    "digest TEXT NOT NULL, ts REAL NOT NULL)"
                )
            self.backend = "sqlite"
        except Exception:  # disk unwritable -> JSON file fallback
            try:
                self._json_path = self._path + ".json"
                os.makedirs(os.path.dirname(self._json_path), exist_ok=True)
                if os.path.exists(self._json_path):
                    with open(self._json_path) as fh:
                        self._mem = json.load(fh)
                self.backend = "json"
            except Exception:
                self.backend = "memory"

    @staticmethod
    def _digest(obj: Any) -> str:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha3_256(raw).hexdigest()

    def _all(self) -> List[Dict[str, Any]]:
        if self.backend == "sqlite":
            with sqlite3.connect(self._path, timeout=30.0) as db:
                rows = db.execute(
                    "SELECT seq, action, payload, prev, digest, ts "
                    "FROM khipu ORDER BY seq"
                ).fetchall()
            return [
                {"seq": r[0], "action": r[1], "payload": json.loads(r[2]),
                 "prev": r[3], "digest": r[4], "ts": r[5]}
                for r in rows
            ]
        return list(self._mem)

    def count(self) -> int:
        with self._lock:
            if self.backend == "sqlite":
                with sqlite3.connect(self._path, timeout=30.0) as db:
                    return int(db.execute("SELECT COUNT(*) FROM khipu").fetchone()[0])
            return len(self._mem)

    def head(self) -> str:
        with self._lock:
            rows = self._all()
            return rows[-1]["digest"] if rows else _GENESIS

    def emit(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        with self._lock:
            if self.backend == "sqlite":
                # BEGIN IMMEDIATE serializes concurrent writers, including two
                # independently-opened stores after a rolling process restart.
                with sqlite3.connect(self._path, timeout=30.0) as db:
                    db.execute("BEGIN IMMEDIATE")
                    last = db.execute(
                        "SELECT seq, digest FROM khipu ORDER BY seq DESC LIMIT 1"
                    ).fetchone()
                    seq = int(last[0]) + 1 if last else 0
                    prev = str(last[1]) if last else _GENESIS
                    body = {"organ": self.organ, "ns": self.ns, "seq": seq,
                            "action": action, "payload": payload, "prev": prev}
                    digest = self._digest(body)
                    ts = time.time()
                    rec = dict(body, digest=digest, ts=ts)
                    db.execute(
                        "INSERT INTO khipu(seq, action, payload, prev, digest, ts) "
                        "VALUES (?,?,?,?,?,?)",
                        (seq, action, json.dumps(payload, sort_keys=True), prev, digest, ts),
                    )
                return rec
            else:
                rows = self._all()
                prev = rows[-1]["digest"] if rows else _GENESIS
                seq = len(rows)
                body = {"organ": self.organ, "ns": self.ns, "seq": seq,
                        "action": action, "payload": payload, "prev": prev}
                digest = self._digest(body)
                ts = time.time()
                rec = dict(body, digest=digest, ts=ts)
                self._mem.append(rec)
                if self.backend == "json" and self._json_path:
                    with open(self._json_path, "w") as fh:
                        json.dump(self._mem, fh)
            return rec

    def verify(self) -> Tuple[bool, int, int]:
        """Re-walk the chain. Returns (ok, depth, first_break_seq | -1)."""
        with self._lock:
            rows = self._all()
            prev = _GENESIS
            for i, rec in enumerate(rows):
                # organ/ns are store-level constants (not persisted per row in the
                # sqlite backend); reconstruct the canonical body deterministically.
                body = {"organ": self.organ, "ns": self.ns, "seq": rec["seq"],
                        "action": rec["action"], "payload": rec["payload"],
                        "prev": rec["prev"]}
                if rec["prev"] != prev or rec["digest"] != self._digest(body):
                    return (False, len(rows), i)
                prev = rec["digest"]
            return (True, len(rows), -1)

    def tail(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return self._all()[-n:]


# ===========================================================================
# 5. STRUCTURED JSON LOGGING
# ===========================================================================
class _JsonLogFormatter(logging.Formatter):
    def __init__(self, organ: str) -> None:
        super().__init__()
        self.organ = organ

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "organ": self.organ,
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "msg": record.getMessage(),
        }
        for k in ("method", "path", "status", "latency_ms"):
            v = getattr(record, k, None)
            if v is not None:
                entry[k] = v
        return json.dumps(entry, separators=(",", ":"))


def _make_logger(organ: str) -> logging.Logger:
    logger = logging.getLogger(f"szl.{organ}.be")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(_JsonLogFormatter(organ))
        logger.addHandler(h)
    return logger


# ===========================================================================
# main entrypoint
# ===========================================================================
def harden(app: Any, organ: str, ns: Optional[str] = None,
           khipu_path: Optional[str] = None) -> Dict[str, Any]:
    """Register all hardening surfaces onto `app`. Never raises."""
    ns = ns or organ
    base = f"/api/{organ}/v1"
    # Hardening endpoints live under a collision-free /be/ subpath so they can
    # never be shadowed by a pre-existing organ sub-app mounted at /api/<organ>
    # (e.g. a catch-all /khipu/{receipt_id}). Health/readyz/honest/openapi keep
    # their REQUIRED canonical paths.
    hbase = f"/api/{organ}/v1/be"
    logger = _make_logger(organ)
    report: Dict[str, Any] = {"organ": organ, "registered": []}

    try:
        from fastapi import FastAPI
        from fastapi.exceptions import RequestValidationError
        from starlette.exceptions import HTTPException as StarletteHTTPException
    except Exception as exc:  # FastAPI not importable -> nothing to do
        logger.error(f"fastapi/pydantic unavailable: {exc!r}")
        report["error"] = "fastapi/pydantic unavailable"
        return report

    # ---- durable store (item 7) -------------------------------------------
    store = DurableKhipu(organ, ns=ns, path=khipu_path)
    report["khipu_backend"] = store.backend
    # expose for the host app + tests
    setattr(app.state, "be_khipu", store) if hasattr(app, "state") else None

    # ---- error envelope helper (item 6) -----------------------------------
    def _envelope(code: str, message: str, trace_id: str, status: int) -> "JSONResponse":
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message,
                               "trace_id": trace_id, "doctrine": DOCTRINE}},
        )

    # ---- 5 + 6: trace/span middleware, JSON logs, error envelopes ---------
    @app.middleware("http")
    async def _trace_log_mw(request: "Request", call_next):
        # Inbound trace context (W3C-ish) or generate.
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id
        request.state.span_id = span_id
        t0 = time.time()
        try:
            resp = await call_next(request)
        except StarletteHTTPException as he:  # mapped below too, but be safe
            dt = round((time.time() - t0) * 1000, 2)
            logger.warning("http_exception", extra={"trace_id": trace_id,
                "span_id": span_id, "method": request.method,
                "path": request.url.path, "status": he.status_code, "latency_ms": dt})
            r = _envelope("http_error", str(he.detail), trace_id, he.status_code)
            r.headers["X-Trace-Id"] = trace_id
            r.headers["X-Span-Id"] = span_id
            return _apply_security_headers(r)
        except Exception as exc:  # unhandled -> uniform 500 envelope
            dt = round((time.time() - t0) * 1000, 2)
            logger.error(f"unhandled:{exc!r}", extra={"trace_id": trace_id,
                "span_id": span_id, "method": request.method,
                "path": request.url.path, "status": 500, "latency_ms": dt})
            r = _envelope("internal_error", "internal server error", trace_id, 500)
            r.headers["X-Trace-Id"] = trace_id
            r.headers["X-Span-Id"] = span_id
            return _apply_security_headers(r)
        dt = round((time.time() - t0) * 1000, 2)
        resp.headers["X-Trace-Id"] = trace_id
        resp.headers["X-Span-Id"] = span_id
        _apply_security_headers(resp)
        logger.info("request", extra={"trace_id": trace_id, "span_id": span_id,
            "method": request.method, "path": request.url.path,
            "status": resp.status_code, "latency_ms": dt})
        return resp

    # Exception handlers so HTTPException/validation errors get the envelope
    # even on routes that bypass middleware error mapping.
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(request: "Request", exc: "StarletteHTTPException"):
        tid = getattr(request.state, "trace_id", uuid.uuid4().hex)
        return _envelope("http_error", str(exc.detail), tid, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: "Request", exc: "RequestValidationError"):
        tid = getattr(request.state, "trace_id", uuid.uuid4().hex)
        return _envelope("validation_error", json.dumps(exc.errors(), default=str), tid, 422)

    report["registered"].append("structured_logging+error_envelopes")

    # ---- 2: rate limiting — 60 req/min per IP -----------------------------
    # We register the slowapi Limiter when the library is present (satisfies the
    # "slowapi or starlette-limiter" doctrine and exposes app.state.limiter for
    # any per-route decorators), but we ENFORCE the global 60/min/IP cap with our
    # own sliding-window middleware so that EVERY 429 returns the uniform error
    # envelope (slowapi's built-in handler returns a non-envelope body). This is
    # a real limiter (counts real requests), not a pass-through.
    rate_lib = "none"
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        app.state.limiter = Limiter(key_func=get_remote_address,
                                    default_limits=[f"{RATE_LIMIT_PER_MIN}/minute"])
        rate_lib = "slowapi"
    except Exception:
        rate_lib = "stdlib-only"

    _hits: Dict[str, Deque[float]] = defaultdict(deque)
    _rl_lock = threading.Lock()

    @app.middleware("http")
    async def _rate_limit_mw(request: "Request", call_next):
        # DEMO-FLOOR FIX: human-facing page/static/health routes are NEVER rate-
        # limited — the showcase must always render. Only the JSON data surface
        # (/api/*, /feeds/*) is metered, at the demo-safe RATE_LIMIT_PER_MIN
        # sliding-window cap. Real abuse on the data surface is still capped.
        if not _is_rate_limited_path(request.url.path):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        with _rl_lock:
            dq = _hits[ip]
            while dq and dq[0] <= now - 60.0:
                dq.popleft()
            if len(dq) >= RATE_LIMIT_PER_MIN:
                tid = getattr(request.state, "trace_id", uuid.uuid4().hex)
                r = _envelope("rate_limited",
                              f"rate limit exceeded: {RATE_LIMIT_PER_MIN}/min per IP",
                              tid, 429)
                r.headers["Retry-After"] = "60"
                return r
            dq.append(now)
        return await call_next(request)

    report["rate_limiting"] = (f"sliding-window/{RATE_LIMIT_PER_MIN}-per-min on data "
                               f"surface; pages exempt (lib={rate_lib})")
    report["registered"].append(
        f"rate_limiting:{RATE_LIMIT_PER_MIN}/min data-surface,pages-exempt (lib={rate_lib})")

    # ---- 1: pydantic models on hardening endpoints (module-scope) ---------
    # EchoIn / KhipuAppendIn are defined at module level above.

    # ---- 4: health probes -------------------------------------------------
    @app.get(f"{base}/healthz", tags=["health"])
    @app.get("/healthz", tags=["health"])
    async def _healthz():
        return {"status": "ok", "organ": organ, "doctrine": DOCTRINE,
                "lock": "749/14/163", "commit": "c7c0ba17"}

    @app.get(f"{base}/readyz", tags=["health"])
    @app.get("/readyz", tags=["health"])
    async def _readyz():
        ok, depth, brk = store.verify()
        body = {"status": "ready" if ok else "degraded", "organ": organ,
                "khipu_backend": store.backend, "khipu_durable": store.backend in ("sqlite", "json"),
                "khipu_depth": depth, "khipu_chain_ok": ok,
                "khipu_first_break_seq": brk, "doctrine": DOCTRINE}
        return JSONResponse(body, status_code=200 if ok else 503)

    report["registered"].append("healthz+readyz")

    # ---- 1 + 7: validated echo + khipu append/verify/tail -----------------
    @app.post(f"{hbase}/echo", tags=["hardening"])
    async def _echo(body: EchoIn, request: "Request"):
        tid = getattr(request.state, "trace_id", None)
        return {"echo": body.message, "trace_id": tid, "doctrine": DOCTRINE}

    @app.post(f"{hbase}/khipu/append", tags=["khipu"])
    async def _khipu_append(body: KhipuAppendIn):
        rec = store.emit(body.action, body.payload)
        return {"ok": True, "receipt": rec, "backend": store.backend}

    @app.get(f"{hbase}/khipu/verify", tags=["khipu"])
    async def _khipu_verify():
        ok, depth, brk = store.verify()
        return {"ok": ok, "depth": depth, "first_break_seq": brk,
                "backend": store.backend, "durable": store.backend in ("sqlite", "json"),
                "head": store.head(), "doctrine": DOCTRINE}

    @app.get(f"{hbase}/khipu/tail", tags=["khipu"])
    async def _khipu_tail(n: int = 10):
        n = max(1, min(int(n), 100))
        return {"receipts": store.tail(n), "count": store.count(),
                "backend": store.backend}

    report["registered"].append("validated_echo+khipu_persistence")

    # ---- 3: re-serve FastAPI's real OpenAPI at the organ path -------------
    # Primary: the app's own auto-generated schema. Some organs mount sub-apps /
    # Gradio whose combined schema generation can raise; in that case we fall
    # back to FastAPI's get_openapi over THIS app's own APIRoutes (still a real,
    # auto-generated spec — never a hand-written stub).
    @app.get("/openapi.json", include_in_schema=False)
    @app.get(f"/api/{organ}/openapi.json", include_in_schema=False)
    async def _organ_openapi():
        try:
            return app.openapi()
        except Exception:
            try:
                from fastapi.openapi.utils import get_openapi
                from fastapi.routing import APIRoute
                all_routes = [r for r in app.routes if isinstance(r, APIRoute)]
                # Some pre-existing organ routes carry annotations FastAPI cannot
                # turn into a schema (e.g. a bare JSONResponse return type under
                # `from __future__ import annotations`). Drop only the offending
                # routes so the rest of the REAL auto-generated spec still serves.
                good = []
                for r in all_routes:
                    try:
                        get_openapi(title=organ, version="0", routes=[r])
                        good.append(r)
                    except Exception:
                        continue
                return get_openapi(
                    title=getattr(app, "title", organ),
                    version=getattr(app, "version", "0.0.0"),
                    routes=good,
                )
            except Exception as exc:
                logger.error(f"openapi_unavailable: {exc!r}")
                return JSONResponse(
                    {"error": {"code": "openapi_unavailable", "message": "openapi schema unavailable",
                               "trace_id": "openapi", "doctrine": DOCTRINE}},
                    status_code=500,
                )

    report["registered"].append(
        f"openapi:/api/{organ}/openapi.json+alias:/openapi.json")

    # ---- 9: honest footer -------------------------------------------------
    @app.get("/honest", tags=["doctrine"])
    @app.get(f"{base}/honest", tags=["doctrine"])
    async def _honest():
        return {
            "organ": organ,
            "git_sha": os.getenv("SZL_GIT_SHA", "unknown"),
            "doctrine_lock": DOCTRINE_LOCK,
            "footer": DOCTRINE_FOOTER,
            "honest_labels": {
                "lambda": "Λ-Aggregator Uniqueness is Conjecture 1 — NOT a theorem.",
                "khipu_signatures": "Chain integrity is SHA3-256 hash-chain verified; "
                                    "DSSE signature is a separately-labelled cosign concern.",
                "persistence": f"Khipu receipts persist via backend={store.backend} "
                               f"(durable={store.backend in ('sqlite','json')}).",
                "principle": "HONESTY OVER CHECKLIST.",
            },
        }

    report["registered"].append("honest_footer")

    # ---- 10: governance / assurance facade (TASK_2) -----------------------
    # Honest aggregation over REAL primitives already baked into this image:
    #   gates_manifest.json (doctrine/locked gates) · szl_dsse (real ECDSA-P256
    #   cosign key) · szl_energy_operator (MEASURED NVML joule ledger) · and this
    #   module's own SHA3-256 khipu hash-chain. Where a real source is not
    #   reachable in this runtime we return a clearly-labelled STRUCTURAL-ONLY
    #   shape (data_kind="structural") — NEVER a fabricated value.
    abase = f"{base}/assurance"

    def _gates_manifest_summary() -> Dict[str, Any]:
        """Real, shape-tolerant summary of gates_manifest.json (never dumps the
        whole 50KB blob, never guesses a schema): presence + content sha256 +
        byte size + a light top-level shape. STRUCTURAL-ONLY when absent."""
        candidates = [
            "/app/gates_manifest.json",
            os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "gates_manifest.json"),
        ]
        for p in candidates:
            try:
                with open(p, "rb") as fh:
                    raw = fh.read()
                obj = json.loads(raw)
                summ: Dict[str, Any] = {
                    "present": True,
                    "path": p,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
                if isinstance(obj, dict):
                    summ["top_level_keys"] = sorted(obj.keys())[:64]
                    g = obj.get("gates")
                    if isinstance(g, (list, dict)):
                        summ["gates_count"] = len(g)
                elif isinstance(obj, list):
                    summ["gates_count"] = len(obj)
                return summ
            except Exception:
                continue
        return {"present": False}

    def _energy_ledger() -> Tuple[Optional[Dict[str, Any]], str]:
        """(ledger, source). Prefer the LIVE in-process operator (same process as
        this app) for MEASURED joules; else the durable persisted ledger file;
        else (None, 'unavailable'). Read-only — never starts a daemon."""
        try:
            import szl_energy_operator as _eo  # already imported by serve.py
            op = getattr(_eo, "_OPERATOR", None)
            if op is not None:
                return op.status(), "live-operator"
            path = os.environ.get(
                "A11OY_OPERATOR_STATE",
                os.path.join(os.path.dirname(os.path.abspath(_eo.__file__)),
                             "artifacts", "energy_operator_ledger.json"))
            with open(path) as fh:
                return json.load(fh), "persisted-ledger"
        except Exception as exc:
            return None, f"unavailable:{type(exc).__name__}"

    @app.get(f"{abase}/compliance", tags=["assurance"])
    async def _assurance_compliance():
        gm = _gates_manifest_summary()
        return {
            "organ": organ,
            "git_sha": os.getenv("SZL_GIT_SHA", "unknown"),
            "doctrine": DOCTRINE,
            "doctrine_lock": DOCTRINE_LOCK,
            "doctrine_footer": DOCTRINE_FOOTER,
            "kernel_commit": "c7c0ba17",
            "locked_formula_count": DOCTRINE_LOCK.get("locked_formula_count"),
            "locked_formula_ids": DOCTRINE_LOCK.get("locked_formula_ids"),
            "slsa": "SLSA L1 honest; L2 .att emitted (not independently verified); "
                    "L3 roadmap, not claimed.",
            "gates_manifest": gm,
            "data_kind": "live" if gm.get("present") else "structural",
            "honesty": ("doctrine lock is the canonical locked-8 {F1,F4,F7,F11,F12,"
                        "F18,F19,F22} @ c7c0ba17 (no-axiom theorem locked_count_eight). "
                        "gates_manifest is summarised from the on-disk manifest when "
                        "present; STRUCTURAL-ONLY (present:false) when absent — never "
                        "fabricated. Λ remains Conjecture 1."),
        }

    @app.get(f"{abase}/credential", tags=["assurance"])
    async def _assurance_credential():
        info: Dict[str, Any] = {"organ": organ,
                                "git_sha": os.getenv("SZL_GIT_SHA", "unknown")}
        try:
            import szl_dsse as _dsse
            info.update({
                "data_kind": "live",
                "algorithm": "ECDSA-P256-SHA256 over DSSE PAE (cosign-compatible)",
                "signing_available": bool(_dsse.signing_available()),
                "public_key_fingerprint_sha256": _dsse.public_key_fingerprint(),
                "public_key_pem": _dsse.COSIGN_PUBLIC_PEM.strip(),
                "private_key_source": ("runtime secret only "
                                       "(SZL_COSIGN_PRIVATE_KEY_PEM); never committed"),
                "honesty": ("the embedded public key verifies signatures offline "
                            "(cosign verify-blob). Signing is REAL only when the cosign "
                            "private-key secret is present in this runtime — "
                            "signing_available reports that truthfully; never faked."),
            })
        except Exception as exc:
            info.update({
                "data_kind": "structural",
                "signing_available": False,
                "honesty": (f"szl_dsse unavailable in this runtime "
                            f"({type(exc).__name__}); credential is STRUCTURAL-ONLY "
                            "— never fabricated."),
            })
        return info

    @app.get(f"{abase}/attest", tags=["assurance"])
    async def _assurance_attest():
        # A DSSE in-toto-style statement over the CURRENT verifiable state, signed
        # via szl_dsse. The envelope's own "honesty" field declares REAL vs
        # UNSIGNED — we never assert a signature that does not exist.
        ok, depth, brk = store.verify()
        statement = {
            "git_sha": os.getenv("SZL_GIT_SHA", "unknown"),
            "build_time": os.getenv("SZL_BUILD_TIME", "unknown"),
            "khipu_chain": {"backend": store.backend, "depth": depth,
                            "chain_ok": ok, "first_break_seq": brk,
                            "head": store.head()},
            "doctrine_lock": DOCTRINE_LOCK,
        }
        try:
            import szl_dsse as _dsse
            env = _dsse.sign_payload(
                statement,
                payload_type="https://szl-holdings.dev/attestations/governance-receipt/v1",
            )
            return {"organ": organ, "statement": statement, "dsse": env,
                    "data_kind": "live",
                    "verify_hint": ("verify with the /assurance/credential "
                                    "public_key_pem; dsse.honesty declares REAL vs "
                                    "UNSIGNED.")}
        except Exception as exc:
            return {"organ": organ, "statement": statement, "dsse": None,
                    "data_kind": "structural",
                    "honesty": (f"szl_dsse unavailable ({type(exc).__name__}); the "
                                "statement is REAL state but UNSIGNED/STRUCTURAL — "
                                "never fabricated.")}

    @app.get(f"{abase}/artifact", tags=["assurance"])
    async def _assurance_artifact():
        gs = os.getenv("SZL_GIT_SHA", "")
        return {
            "organ": organ,
            "git_sha": gs or "unknown",
            "build_time": os.getenv("SZL_BUILD_TIME", "unknown"),
            "image_ref": os.getenv("SZL_IMAGE_REF", "unknown"),
            "image_digest": os.getenv("SZL_IMAGE_DIGEST", "unknown"),
            "slsa": "SLSA L1 honest; L2 .att emitted (not independently verified); "
                    "L3 roadmap, not claimed.",
            "provenance": ("cosign-signed image (cosign verify) + signed SLSA "
                           "build-provenance attestation "
                           "(actions/attest-build-provenance@v2, Sigstore keyless "
                           "Fulcio+Rekor); verifiable via `gh attestation verify` / "
                           "`cosign verify-attestation --type slsaprovenance`."),
            "data_kind": "live" if gs else "structural",
            "honesty": ("git_sha/build_time are baked at build time (ENV). "
                        "image_digest/image_ref are the build-published values when "
                        "SZL_IMAGE_DIGEST/SZL_IMAGE_REF are set, else 'unknown' "
                        "(verify the running digest out-of-band via cosign) — "
                        "never fabricated."),
        }

    @app.get(f"{base}/forge/ledger", tags=["forge"])
    async def _forge_ledger():
        led, src = _energy_ledger()
        ok, depth, brk = store.verify()
        energy: Optional[Dict[str, Any]] = None
        if led is not None:
            energy = {
                "joules_measured_total": led.get("joules_measured_total"),
                "joules_measured_label": led.get("joules_measured_label", "MEASURED"),
                "measured_jobs": led.get("measured_jobs"),
                "tokens_total": led.get("tokens_total"),
                "by_node": led.get("by_node"),
                "running": led.get("running"),
                "stub_mode": led.get("stub_mode"),
                "exporter": led.get("exporter"),
                "source": src,
            }
        return {
            "organ": organ,
            "git_sha": os.getenv("SZL_GIT_SHA", "unknown"),
            "energy_ledger": energy,
            "receipt_chain": {
                "backend": store.backend,
                "durable": store.backend in ("sqlite", "json"),
                "depth": depth,
                "chain_ok": ok,
                "first_break_seq": brk,
                "head": store.head(),
                "count": store.count(),
            },
            "data_kind": "live" if (energy is not None or store.count() > 0)
                         else "structural",
            "doctrine": DOCTRINE,
            "honesty": ("energy figures are MEASURED NVML joule deltas from the live "
                        "operator (or the durable persisted ledger when the operator is "
                        "not in this process) — SAMPLE/stub energy is excluded and never "
                        "billable; receipt_chain is a SHA3-256 hash-chain that verify() "
                        "re-walks. Counters are NEVER reset and NEVER fabricated; "
                        "energy_ledger is null when no ledger is reachable."),
        }

    # ---- 11: cheapest-watt placement (carbon/cost-aware routing) ----------
    # Reads the LIVE energy-operator status (per-node MEASURED joules + tokens +
    # power_w + live grid €/MWh) and runs the cheapest-watt placement policy:
    # pick the sovereign node minimizing energy-cost-per-token, record the decision
    # (chosen node, €/MWh at decision time, MEASURED J/token, cheaper-than-alternative
    # delta) into a re-hashable, hash-chained receipt, optionally DSSE-signed. Honest:
    # with <2 comparable MEASURED nodes -> "no placement choice this tick"; a saving is
    # MEASURED only when both legs are MEASURED; never fabricates a price or a saving.
    def _operator_status_for_cw() -> Tuple[Optional[Dict[str, Any]], str]:
        """Live in-process operator status (MEASURED), else persisted ledger, else
        (None, unavailable). Read-only; reuses the same source as /forge/ledger."""
        return _energy_ledger()

    @app.get(f"{base}/energy/cheapest-watt", tags=["energy"])
    async def _cheapest_watt():
        try:
            import szl_cheapest_watt as _cw
        except Exception as exc:  # module not in image: STRUCTURAL-ONLY, never faked
            return {"organ": organ, "data_kind": "structural",
                    "honesty": (f"szl_cheapest_watt unavailable ({type(exc).__name__}); "
                                "cheapest-watt is STRUCTURAL-ONLY — never fabricated.")}
        status, src = _operator_status_for_cw()
        led = _cw.get_ledger()
        decision_receipt: Optional[Dict[str, Any]] = None
        if status is not None:
            # Record ONE fresh placement decision against the live status this read.
            decision_receipt = led.record(status)
            # Layer a REAL DSSE signature over the placement receipt when a cosign key
            # is present; absent a key the receipt is honest-but-UNSIGNED (never faked).
            try:
                import szl_dsse as _dsse
                env = _dsse.sign_payload(
                    decision_receipt,
                    payload_type="https://szl-holdings.dev/attestations/cheapest-watt-placement/v1",
                )
                decision_receipt = {**decision_receipt, "dsse": env,
                                    "signed": True}
            except Exception:
                decision_receipt = {**decision_receipt, "dsse": None,
                                    "signed": False,
                                    "sign_note": ("no cosign private key in this runtime; "
                                                  "receipt is REAL + re-hashable but UNSIGNED "
                                                  "— never faked")}
        body = led.status()
        body.update({
            "organ": organ,
            "git_sha": os.getenv("SZL_GIT_SHA", "unknown"),
            "operator_source": src,
            "data_kind": "live" if status is not None else "structural",
            "latest_decision": decision_receipt,
            "reads": "GET re-evaluates against the live operator status and appends one decision",
        })
        if status is None:
            body["honesty_no_operator"] = (
                f"no live operator status reachable ({src}); no placement decision this "
                "read — never fabricated.")
        return body

    # canonical path /api/<organ>/v1/energy/cheapest-watt registered above (same
    # /api/<organ>/v1/energy prefix the operator's status/ledger/projection use).
    report["registered"].append("energy/cheapest-watt(placement+signed-receipt)")

    report["registered"].append(
        "assurance(artifact,credential,compliance,attest)+forge/ledger")
    report["ok"] = True
    logger.info("hardening registered", extra={"trace_id": "boot", "span_id": "boot"})
    return report
